package com.getjobs.common.util;

public class RateLimitException extends RuntimeException {
    public RateLimitException(String message) {
        super(message);
    }
}
