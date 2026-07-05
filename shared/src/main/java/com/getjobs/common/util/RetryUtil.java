package com.getjobs.common.util;

import lombok.extern.slf4j.Slf4j;

import java.util.concurrent.ThreadLocalRandom;
import java.util.function.Supplier;

/**
 * Retry utility with exponential backoff for network operations.
 * Prevents overwhelming external services and handles transient failures.
 */
@Slf4j
public final class RetryUtil {

    private RetryUtil() {}

    /**
     * Retry a callable with exponential backoff
     *
     * @param operation The operation to retry
     * @param maxAttempts Maximum number of attempts
     * @param baseDelayMs Base delay in milliseconds (actual delay = baseDelay * 2^attempt)
     * @param <T> Return type
     * @return The result of the operation
     * @throws Exception if all retries fail
     */
    public static <T> T retry(Supplier<T> operation, int maxAttempts, long baseDelayMs) throws Exception {
        Exception lastException = null;

        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                return operation.get();
            } catch (Exception e) {
                lastException = e;

                if (attempt == maxAttempts) {
                    log.warn("Retry exhausted after {} attempts. Last error: {}", maxAttempts, e.getMessage());
                    break;
                }

                long delay = calculateBackoffDelay(attempt, baseDelayMs);
                log.warn("Attempt {}/{} failed: {}. Retrying in {}ms...",
                        attempt, maxAttempts, e.getMessage(), delay);

                try {
                    Thread.sleep(delay);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    log.warn("Retry interrupted at attempt {}/{}", attempt, maxAttempts);
                    break;
                }
            }
        }

        throw lastException != null
                ? lastException
                : new RuntimeException("Retry operation failed after " + maxAttempts + " attempts (no exception recorded)");
    }

    /**
     * Retry a callable with exponential backoff, returning null on failure
     */
    public static <T> T retryOrNull(Supplier<T> operation, int maxAttempts, long baseDelayMs) {
        try {
            return retry(operation, maxAttempts, baseDelayMs);
        } catch (Exception e) {
            log.error("Retry operation failed after {} attempts, returning null", maxAttempts);
            return null;
        }
    }

    /**
     * Calculate exponential backoff delay with jitter
     */
    private static long calculateBackoffDelay(int attempt, long baseDelayMs) {
        long exponentialDelay = baseDelayMs * (1L << (attempt - 1));
        long cappedDelay = Math.min(exponentialDelay, 30_000);
        long jitter = (long) (cappedDelay * 0.2 * (ThreadLocalRandom.current().nextDouble() * 2 - 1));
        long delay = cappedDelay + jitter;
        return Math.max(0, delay); // Ensure non-negative
    }

    /**
     * Default retry configuration for API calls
     */
    public static <T> T retryApiCall(Supplier<T> operation) {
        return retryOrNull(operation, 3, 1000);
    }

    /**
     * Default retry configuration for browser operations
     */
    public static <T> T retryBrowserOperation(Supplier<T> operation) {
        return retryOrNull(operation, 2, 500);
    }
}
