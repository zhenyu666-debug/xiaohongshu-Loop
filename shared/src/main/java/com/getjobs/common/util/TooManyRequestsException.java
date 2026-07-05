package com.getjobs.common.util;

/**
 * Exception thrown when HTTP 429 (Too Many Requests) is received.
 * Contains retry-after information from the server.
 */
public class TooManyRequestsException extends RuntimeException {
    private final long retryAfterSeconds;

    public TooManyRequestsException(String message, long retryAfterSeconds) {
        super(message);
        this.retryAfterSeconds = retryAfterSeconds;
    }

    public TooManyRequestsException(String message) {
        this(message, -1);
    }

    /**
     * Get the retry-after delay in seconds.
     * @return retry-after seconds, or -1 if not specified
     */
    public long getRetryAfterSeconds() {
        return retryAfterSeconds;
    }

    /**
     * Check if retry-after was specified.
     */
    public boolean hasRetryAfter() {
        return retryAfterSeconds > 0;
    }
}
