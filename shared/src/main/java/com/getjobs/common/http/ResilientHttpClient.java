package com.getjobs.common.http;

import com.getjobs.common.config.HttpClientConfig;
import com.getjobs.common.logging.StructuredLogger;
import com.getjobs.common.util.CircuitBreaker;
import com.getjobs.common.util.RateLimiter;
import com.getjobs.common.util.RetryUtil;
import com.getjobs.common.util.TooManyRequestsException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Enhanced HTTP Client with retry, circuit breaker, and rate limiting.
 * Provides resilient HTTP communication for external APIs.
 */
@Slf4j
@Component
public class ResilientHttpClient {

    private final HttpClientConfig config;
    private final HttpClient httpClient;
    private final Map<String, CircuitBreaker> circuitBreakers = new ConcurrentHashMap<>();
    private final Map<String, RateLimiter> rateLimiters = new ConcurrentHashMap<>();

    public ResilientHttpClient(HttpClientConfig config) {
        this.config = config;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(config.getConnectTimeout())
                .build();
    }

    /**
     * Execute HTTP GET with resilience patterns
     */
    public Optional<String> get(String url) {
        return get(url, Map.of());
    }

    public Optional<String> get(String url, Map<String, String> headers) {
        return executeWithResilience("GET", url, headers, null);
    }

    /**
     * Execute HTTP POST with resilience patterns
     */
    public Optional<String> post(String url, String body) {
        return post(url, Map.of(), body);
    }

    public Optional<String> post(String url, Map<String, String> headers, String body) {
        return executeWithResilience("POST", url, headers, body);
    }

    /**
     * Execute HTTP request with retry, circuit breaker, and rate limiting
     */
    private Optional<String> executeWithResilience(String method, String url,
                                                   Map<String, String> headers, String body) {
        String host = extractHost(url);

        // Get or create circuit breaker for this host
        CircuitBreaker breaker = circuitBreakers.computeIfAbsent(host,
                k -> CircuitBreaker.of(k));

        // Get or create rate limiter for this host
        RateLimiter limiter = rateLimiters.computeIfAbsent(host,
                k -> RateLimiter.of(60)); // 60 requests per minute default

        // Check rate limit
        if (!limiter.tryAcquire()) {
            log.warn("Rate limit exceeded for host: {}", host);
            return Optional.empty();
        }

        // Check circuit breaker
        if (!breaker.isCallPermitted()) {
            log.warn("Circuit breaker open for host: {}", host);
            return Optional.empty();
        }

        // Execute with retry (respect retry-after for 429 responses)
        try {
            String result = RetryUtil.retryOrNull(() -> {
                try {
                    return executeHttpRequest(method, url, headers, body);
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            }, config.getMaxRetries(), config.getRetryBaseDelayMs());

            if (result != null) {
                breaker.recordSuccess();
                return Optional.of(result);
            }
        } catch (Exception e) {
            log.error("HTTP request failed after retries: {} {} - {}",
                    method, url, e.getMessage());
            breaker.recordFailure(e);
        }

        return Optional.empty();
    }

    private String executeHttpRequest(String method, String rawUrl,
                                      Map<String, String> headers, String body) throws Exception {
        long startTime = System.currentTimeMillis();

        URI uri;
        try {
            uri = URI.create(rawUrl);
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("Invalid URL: " + rawUrl, e);
        }

        HttpRequest.Builder builder = HttpRequest.newBuilder()
                .uri(uri)
                .timeout(config.getReadTimeout());

        // Add default headers
        builder.header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36");
        builder.header("Accept", "application/json, text/html, */*");

        // Add custom headers
        headers.forEach(builder::header);

        // Set body if present
        if (body != null && (method.equals("POST") || method.equals("PUT") || method.equals("PATCH"))) {
            builder.header("Content-Type", "application/json; charset=UTF-8");
            builder.POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8));
        } else {
            builder.GET();
        }

        HttpRequest request = builder.build();

        try {
            HttpResponse<String> response = httpClient.send(request,
                    HttpResponse.BodyHandlers.ofString());

            long duration = System.currentTimeMillis() - startTime;

            StructuredLogger.info("HTTP Request completed",
                    "method", method,
                    "url", rawUrl,
                    "status", String.valueOf(response.statusCode()),
                    "duration_ms", String.valueOf(duration));

            if (response.statusCode() >= 500) {
                throw new HttpException(response.statusCode(), "Server error: " + response.body());
            }

            // Handle HTTP 429 Too Many Requests
            if (response.statusCode() == 429) {
                long retryAfter = parseRetryAfterHeader(response.headers().firstValue("Retry-After").orElse(null));
                String message = "Rate limited (429): " + rawUrl;
                throw new TooManyRequestsException(message, retryAfter);
            }

            return response.body();
        } catch (java.net.SocketTimeoutException e) {
            StructuredLogger.error("HTTP Request timeout",
                    e,
                    "method", method,
                    "url", rawUrl,
                    "timeout_ms", String.valueOf(config.getReadTimeoutSeconds() * 1000));
            throw e;
        }
    }

    private String extractHost(String url) {
        try {
            URI uri = URI.create(url);
            String host = uri.getHost();
            if (host == null) {
                log.warn("Invalid URL - no host found: {}", url);
                throw new IllegalArgumentException("Invalid URL - no host found: " + url);
            }
            return host;
        } catch (IllegalArgumentException e) {
            throw e;
        } catch (Exception e) {
            log.warn("Failed to parse URL '{}': {}", url, e.getMessage());
            throw new IllegalArgumentException("Failed to parse URL: " + url, e);
        }
    }

    /**
     * Get circuit breaker status
     */
    public CircuitBreaker.State getCircuitBreakerState(String host) {
        CircuitBreaker breaker = circuitBreakers.get(host);
        return breaker != null ? breaker.getState() : CircuitBreaker.State.CLOSED;
    }

    /**
     * Reset circuit breaker for a host
     */
    public void resetCircuitBreaker(String host) {
        CircuitBreaker breaker = circuitBreakers.get(host);
        if (breaker != null) {
            breaker.reset();
        }
    }

    /**
     * Custom HTTP exception
     */
    public static class HttpException extends RuntimeException {
        private final int statusCode;

        public HttpException(int statusCode, String message) {
            super(message);
            this.statusCode = statusCode;
        }

        public int getStatusCode() {
            return statusCode;
        }
    }

    /**
     * Parse Retry-After header value to seconds.
     * Supports both HTTP-date and delta-seconds formats.
     */
    private long parseRetryAfterHeader(String retryAfter) {
        if (retryAfter == null || retryAfter.isBlank()) {
            return -1;
        }
        try {
            return Long.parseLong(retryAfter.trim());
        } catch (NumberFormatException e) {
            try {
                java.time.Instant instant = java.time.Instant.parse(retryAfter.trim());
                long seconds = java.time.Duration.between(java.time.Instant.now(), instant).getSeconds();
                return Math.max(0, seconds);
            } catch (Exception dateParseError) {
                log.warn("Failed to parse Retry-After header: {}", retryAfter);
                return -1;
            }
        }
    }
}
