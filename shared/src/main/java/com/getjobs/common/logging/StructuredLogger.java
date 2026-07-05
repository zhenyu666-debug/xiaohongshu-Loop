package com.getjobs.common.logging;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;

import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.Supplier;

/**
 * Structured JSON logging utility for consistent, machine-readable log output.
 * Provides request/response logging with sensitive data redaction.
 */
@Slf4j
public final class StructuredLogger {

    private static final ThreadLocal<ObjectMapper> MAPPER = ThreadLocal.withInitial(ObjectMapper::new);

    private StructuredLogger() {}

    private static ObjectMapper mapper() {
        return MAPPER.get();
    }

    /**
     * Log an info message with structured context
     */
    public static void info(String message, Map<String, Object> context) {
        logWithLevel("INFO", message, context, null);
    }

    /**
     * Log an info message with key-value pairs
     */
    public static void info(String message, String... keyValues) {
        info(message, toMap(keyValues));
    }

    /**
     * Log a warning message with structured context
     */
    public static void warn(String message, Map<String, Object> context) {
        logWithLevel("WARN", message, context, null);
    }

    /**
     * Log a warning message with key-value pairs
     */
    public static void warn(String message, String... keyValues) {
        warn(message, toMap(keyValues));
    }

    /**
     * Log an error with exception
     */
    public static void error(String message, Throwable throwable, Map<String, Object> context) {
        Map<String, Object> ctx = new HashMap<>(context);
        ctx.put("error_type", throwable.getClass().getSimpleName());
        ctx.put("error_message", throwable.getMessage());
        logWithLevel("ERROR", message, ctx, throwable);
    }

    /**
     * Log an error with exception and key-value pairs
     */
    public static void error(String message, Throwable throwable, String... keyValues) {
        error(message, throwable, toMap(keyValues));
    }

    /**
     * Log an error message
     */
    public static void error(String message, Map<String, Object> context) {
        logWithLevel("ERROR", message, context, null);
    }

    /**
     * Log with level and context
     */
    private static void logWithLevel(String level, String message, Map<String, Object> context, Throwable throwable) {
        Map<String, Object> logEntry = new HashMap<>();
        logEntry.put("timestamp", Instant.now().toString());
        logEntry.put("level", level);
        logEntry.put("message", message);
        logEntry.put("logger", "get-jobs");

        if (context != null) {
            logEntry.putAll(context);
        }

        if (throwable != null) {
            logEntry.put("stack_trace", getStackTrace(throwable));
        }

        try {
            String json = mapper().writeValueAsString(logEntry);
            switch (level) {
                case "ERROR" -> org.slf4j.LoggerFactory.getLogger("structured").error(json);
                case "WARN" -> org.slf4j.LoggerFactory.getLogger("structured").warn(json);
                default -> org.slf4j.LoggerFactory.getLogger("structured").info(json);
            }
        } catch (JsonProcessingException e) {
            // Fallback to standard logging
            org.slf4j.LoggerFactory.getLogger("structured").info(message);
        }
    }

    private static String getStackTrace(Throwable t) {
        StringBuilder sb = new StringBuilder();
        for (StackTraceElement element : t.getStackTrace()) {
            if (sb.length() + element.toString().length() + 1 > 1000) {
                sb.append("... (truncated)");
                break;
            }
            sb.append(element.toString()).append("\n");
        }
        return sb.toString();
    }

    /**
     * Log a request with redacted sensitive data
     */
    public static void logRequest(String method, String url, Map<String, String> headers, Map<String, Object> body) {
        Map<String, Object> context = new HashMap<>();
        context.put("event", "http_request");
        context.put("method", method);
        context.put("url", redactUrl(url));
        context.put("headers", redactSensitiveHeaders(headers));

        if (body != null) {
            context.put("body", redactSensitiveData(body));
        }

        info("HTTP Request", context);
    }

    /**
     * Log a response with timing
     */
    public static void logResponse(int statusCode, long durationMs, Map<String, Object> body) {
        Map<String, Object> context = new HashMap<>();
        context.put("event", "http_response");
        context.put("status_code", statusCode);
        context.put("duration_ms", durationMs);

        if (body != null) {
            context.put("body", redactSensitiveData(body));
        }

        if (statusCode >= 500) {
            error("HTTP Response Error", context);
        } else if (statusCode >= 400) {
            warn("HTTP Response Warning", context);
        } else {
            info("HTTP Response", context);
        }
    }

    /**
     * Create a request logger context
     */
    public static RequestLogger startRequest(String operation) {
        return new RequestLogger(operation);
    }

    /**
     * Redact sensitive data from URLs
     */
    private static String redactUrl(String url) {
        if (url == null) return null;
        String redacted = url;
        // Redact query parameters
        redacted = redacted.replaceAll("([?&]token=)[^&]*", "$1***");
        redacted = redacted.replaceAll("([?&]key=)[^&]*", "$1***");
        redacted = redacted.replaceAll("([?&]password=)[^&]*", "$1***");
        redacted = redacted.replaceAll("([?&]cookie=)[^&]*", "$1***");
        redacted = redacted.replaceAll("([?&]api[_-]?key=)[^&]*", "$1***");
        redacted = redacted.replaceAll("([?&]auth=)[^&]*", "$1***");
        // Redact sensitive path segments (UUIDs, long hex strings, base64-like strings)
        redacted = redacted.replaceAll("/([0-9a-f]{32,})/", "/***/");
        redacted = redacted.replaceAll("/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/", "/***/");
        redacted = redacted.replaceAll("/([A-Za-z0-9+/]{32,}=*)/", "/***/");
        return redacted;
    }

    /**
     * Redact sensitive headers
     */
    private static Map<String, String> redactSensitiveHeaders(Map<String, String> headers) {
        if (headers == null) return null;

        Map<String, String> redacted = new HashMap<>();
        String[] sensitiveHeaders = {"authorization", "cookie", "x-api-key", "x-auth-token", "password"};

        for (Map.Entry<String, String> entry : headers.entrySet()) {
            String key = entry.getKey().toLowerCase();
            boolean isSensitive = false;

            for (String sensitive : sensitiveHeaders) {
                if (key.contains(sensitive)) {
                    isSensitive = true;
                    break;
                }
            }

            redacted.put(entry.getKey(), isSensitive ? "***REDACTED***" : entry.getValue());
        }

        return redacted;
    }

    private static final String[] SENSITIVE_KEYS = {"password", "token", "secret", "key", "cookie", "auth", "credential"};

    private static boolean isSensitiveKey(String key) {
        if (key == null) return false;
        String lower = key.toLowerCase();
        for (String s : SENSITIVE_KEYS) {
            if (lower.equals(s) || lower.contains(s)) {
                return true;
            }
        }
        return false;
    }

    private static Object redactRecursive(Object value) {
        if (value == null) return null;
        if (value instanceof Map) {
            Map<?, ?> map = (Map<?, ?>) value;
            Map<String, Object> redacted = new HashMap<>();
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                String k = String.valueOf(entry.getKey());
                if (isSensitiveKey(k)) {
                    redacted.put(k, "***REDACTED***");
                } else {
                    redacted.put(k, redactRecursive(entry.getValue()));
                }
            }
            return redacted;
        }
        if (value instanceof List) {
            List<?> list = (List<?>) value;
            List<Object> redacted = new java.util.ArrayList<>();
            for (Object item : list) {
                redacted.add(redactRecursive(item));
            }
            return redacted;
        }
        return value;
    }

    /**
     * Redact sensitive data from a map (recursively for nested structures)
     */
    private static Map<String, Object> redactSensitiveData(Map<String, Object> data) {
        if (data == null) return null;
        return (Map<String, Object>) redactRecursive(data);
    }

    private static Map<String, Object> toMap(String... keyValues) {
        Map<String, Object> map = new HashMap<>();
        for (int i = 0; i < keyValues.length - 1; i += 2) {
            map.put(keyValues[i], keyValues[i + 1]);
        }
        return map;
    }

    /**
     * Request logger for tracking operation timing and context
     */
    public static class RequestLogger {
        private final String operationId;
        private final String operation;
        private final long startTime;
        private final Map<String, Object> context;

        private RequestLogger(String operation) {
            this.operationId = UUID.randomUUID().toString().substring(0, 8);
            this.operation = operation;
            this.startTime = System.currentTimeMillis();
            this.context = new HashMap<>();
            this.context.put("event", "operation_start");
            this.context.put("operation", operation);
            this.context.put("operation_id", operationId);

            info("Operation started", context);
        }

        public RequestLogger addContext(String key, Object value) {
            context.put(key, value);
            return this;
        }

        public void logSuccess() {
            long duration = System.currentTimeMillis() - startTime;
            Map<String, Object> ctx = new HashMap<>(context);
            ctx.put("event", "operation_complete");
            ctx.put("duration_ms", duration);
            ctx.put("status", "success");

            info("Operation completed", ctx);
        }

        public void logSuccess(Object result) {
            long duration = System.currentTimeMillis() - startTime;
            Map<String, Object> ctx = new HashMap<>(context);
            ctx.put("event", "operation_complete");
            ctx.put("duration_ms", duration);
            ctx.put("status", "success");

            info("Operation completed", ctx);
        }

        public void logFailure(Throwable error) {
            long duration = System.currentTimeMillis() - startTime;
            Map<String, Object> ctx = new HashMap<>(context);
            ctx.put("event", "operation_failed");
            ctx.put("duration_ms", duration);
            ctx.put("status", "failure");

            error("Operation failed", error, ctx);
        }
    }
}
