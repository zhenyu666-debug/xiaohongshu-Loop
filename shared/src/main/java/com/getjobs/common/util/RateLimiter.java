package com.getjobs.common.util;

import lombok.extern.slf4j.Slf4j;

import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Rate limiter to prevent IP blocking from external services.
 * Uses token bucket algorithm for smooth rate limiting.
 */
@Slf4j
public class RateLimiter {

    private final int maxRequests;
    private final long windowMs;
    private final AtomicInteger requestCount = new AtomicInteger(0);
    private final AtomicLong windowStartMs = new AtomicLong(System.currentTimeMillis());

    public RateLimiter(int maxRequestsPerWindow, long windowMs) {
        this.maxRequests = maxRequestsPerWindow;
        this.windowMs = windowMs;
    }

    public static RateLimiter of(int requestsPerMinute) {
        return new RateLimiter(requestsPerMinute, 60_000);
    }

    public static RateLimiter forJobs(int maxPerMinute) {
        return new RateLimiter(maxPerMinute, 60_000);
    }

    /**
     * Try to acquire a permit. Returns true if allowed, false if rate limited.
     * Uses atomic update to combine window check and count increment,
     * preventing stampede during window reset.
     */
    public boolean tryAcquire() {
        long currentTime = System.currentTimeMillis();
        while (true) {
            long startMs = windowStartMs.get();
            if (currentTime - startMs >= windowMs) {
                if (windowStartMs.compareAndSet(startMs, currentTime)) {
                    requestCount.set(1);
                    return true;
                }
                continue;
            }
            int current = requestCount.incrementAndGet();
            if (current > maxRequests) {
                requestCount.decrementAndGet();
                log.debug("Rate limit exceeded: {}/{} requests", current - 1, maxRequests);
                return false;
            }
            return true;
        }
    }

    private static final long MAX_WAIT_MS = 60_000;

    /**
     * Acquire a permit, waiting if necessary
     */
    public void acquire() throws InterruptedException {
        long start = System.currentTimeMillis();
        while (!tryAcquire()) {
            long elapsed = System.currentTimeMillis() - start;
            if (elapsed >= MAX_WAIT_MS) {
                throw new RateLimitException("Rate limit wait exceeded " + MAX_WAIT_MS + "ms");
            }
            long waitTime = Math.min(5000, Math.max(200, 50 * (requestCount.get() - maxRequests + 1)));
            Thread.sleep(Math.min(waitTime, MAX_WAIT_MS - elapsed));
        }
    }

    /**
     * Calculate recommended delay before next request (in milliseconds)
     */
    public long getRecommendedDelay() {
        int count = requestCount.get();
        if (count < maxRequests) {
            return 0;
        }
        double loadFactor = (double) count / maxRequests;
        return (long) (windowMs * loadFactor * 0.1);
    }

    /**
     * Get current usage statistics
     */
    public UsageStats getStats() {
        return new UsageStats(requestCount.get(), maxRequests, windowMs);
    }

    public record UsageStats(int currentCount, int maxRequests, long windowMs) {
        public double getUsagePercent() {
            return (double) currentCount / maxRequests * 100;
        }

        public boolean isNearLimit() {
            return currentCount >= maxRequests * 0.8;
        }
    }
}
