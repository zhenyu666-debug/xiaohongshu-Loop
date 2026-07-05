package com.getjobs.common.util;

import java.util.regex.Pattern;

/**
 * Input sanitization utilities to prevent XSS and injection attacks.
 * All user inputs should be sanitized before use.
 */
public final class InputSanitizer {

    // Dangerous patterns that should be blocked
    private static final Pattern[] DANGEROUS_PATTERNS = {
            Pattern.compile("<script[^>]*>.*?</script>", Pattern.CASE_INSENSITIVE | Pattern.DOTALL),
            Pattern.compile("javascript:", Pattern.CASE_INSENSITIVE),
            Pattern.compile("on\\w+\\s*=", Pattern.CASE_INSENSITIVE),
            Pattern.compile("<iframe[^>]*>.*?</iframe>", Pattern.CASE_INSENSITIVE | Pattern.DOTALL),
            Pattern.compile("eval\\s*\\(", Pattern.CASE_INSENSITIVE),
            Pattern.compile("expression\\s*\\(", Pattern.CASE_INSENSITIVE)
    };

    // SQL injection patterns
    private static final Pattern[] SQL_INJECTION_PATTERNS = {
            Pattern.compile("('|(\"))(.*?)\\1\\s*(OR|AND)", Pattern.CASE_INSENSITIVE),
            Pattern.compile("(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\\s", Pattern.CASE_INSENSITIVE),
            Pattern.compile(";\\s*(DROP|DELETE|TRUNCATE)", Pattern.CASE_INSENSITIVE),
            Pattern.compile("--\\s*$", Pattern.MULTILINE),
            Pattern.compile("/\\*.*?\\*/", Pattern.DOTALL)
    };

    private InputSanitizer() {}

    /**
     * Sanitize a string for safe display in HTML context
     */
    public static String sanitizeForHtml(String input) {
        if (input == null) {
            return null;
        }

        String sanitized = input
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;")
                .replace("'", "&#x27;")
                .replace("/", "&#x2F;");

        // Remove dangerous patterns
        for (Pattern pattern : DANGEROUS_PATTERNS) {
            sanitized = pattern.matcher(sanitized).replaceAll("");
        }

        return sanitized;
    }

    /**
     * Sanitize for use in SQL LIKE queries
     */
    public static String sanitizeForLike(String input) {
        if (input == null) {
            return null;
        }
        return input
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_");
    }

    /**
     * Check if input contains potential SQL injection
     */
    public static boolean containsSqlInjection(String input) {
        if (input == null) {
            return false;
        }

        for (Pattern pattern : SQL_INJECTION_PATTERNS) {
            if (pattern.matcher(input).find()) {
                return true;
            }
        }

        return false;
    }

    /**
     * Validate and sanitize a search keyword
     */
    public static String sanitizeSearchKeyword(String keyword) {
        if (keyword == null) {
            return "";
        }

        // Trim and limit length
        String sanitized = keyword.trim();

        // Remove potentially dangerous characters for search
        sanitized = sanitized.replaceAll("[<>\"']", "");

        // Limit length to prevent abuse
        if (sanitized.length() > 100) {
            sanitized = sanitized.substring(0, 100);
        }

        return sanitized;
    }

    /**
     * Sanitize a URL parameter
     */
    public static String sanitizeUrlParam(String param) {
        if (param == null) {
            return null;
        }

        // Remove potentially dangerous URL characters
        String sanitized = param.trim()
                .replaceAll("[<>\"'&]", "")
                .replaceAll("\\s+", " ");

        // Limit length
        if (sanitized.length() > 500) {
            sanitized = sanitized.substring(0, 500);
        }

        return sanitized;
    }

    /**
     * Sanitize for JSON output
     */
    public static String sanitizeForJson(String input) {
        if (input == null) {
            return null;
        }
        return input
                .replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }

    /**
     * Validate that input contains only safe characters for a filename
     */
    public static String sanitizeFilename(String filename) {
        if (filename == null) {
            return null;
        }
        // Remove path traversal and dangerous characters
        return filename
                .replaceAll("[/\\\\:*?\"<>|]", "_")
                .replaceAll("\\.\\.", "_")
                .trim();
    }

    /**
     * Check if input contains XSS patterns
     */
    public static boolean containsXss(String input) {
        if (input == null) {
            return false;
        }

        for (Pattern pattern : DANGEROUS_PATTERNS) {
            if (pattern.matcher(input).find()) {
                return true;
            }
        }

        return false;
    }
}
