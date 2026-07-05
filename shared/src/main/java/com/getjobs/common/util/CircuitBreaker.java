package com.getjobs.common.util;

import lombok.extern.slf4j.Slf4j;

import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Supplier;

/**
 * Circuit breaker implementation for external API calls.
 * Prevents cascading failures and provides fault tolerance.
 *
 * States:
 * - CLOSED: Normal operation, requests pass through
 * - OPEN: Circuit is tripped, requests fail fast
 * - HALF_OPEN: Testing if the service has recovered
 */
@Slf4j
public class CircuitBreaker {

    public enum State {
        CLOSED,
        OPEN,
        HALF_OPEN
    }

    private final String name;
    private final int failureThreshold;
    private final long recoveryTimeoutMs;
    private final int halfOpenMaxCalls;

    private final AtomicReference<State> state = new AtomicReference<>(State.CLOSED);
    private final AtomicInteger failureCount = new AtomicInteger(0);
    private final AtomicInteger halfOpenCalls = new AtomicInteger(0);
    private final AtomicLong lastFailureTime = new AtomicLong(0);

    public CircuitBreaker(String name, int failureThreshold, long recoveryTimeoutMs, int halfOpenMaxCalls) {
        this.name = name;
        this.failureThreshold = failureThreshold;
        this.recoveryTimeoutMs = recoveryTimeoutMs;
        this.halfOpenMaxCalls = halfOpenMaxCalls;
    }

    public static CircuitBreaker of(String name) {
        return new CircuitBreaker(name, 5, 60_000, 3);
    }

    /**
     * Execute an operation with circuit breaker protection
     */
    public <T> T execute(Supplier<T> operation, Supplier<T> fallback) {
        if (!isCallPermitted()) {
            log.debug("Circuit breaker [{}] is OPEN, using fallback", name);
            return fallback != null ? fallback.get() : null;
        }

        try {
            T result = operation.get();
            recordSuccess();
            return result;
        } catch (Exception e) {
            recordFailure(e);
            return fallback != null ? fallback.get() : null;
        }
    }

    /**
     * Execute an operation without fallback
     */
    public <T> T execute(Supplier<T> operation) {
        return execute(operation, null);
    }

    public boolean isCallPermitted() {
        State currentState = state.get();

        switch (currentState) {
            case CLOSED:
                return true;

            case OPEN:
                if (System.currentTimeMillis() - lastFailureTime.get() > recoveryTimeoutMs) {
                    if (state.compareAndSet(State.OPEN, State.HALF_OPEN)) {
                        halfOpenCalls.set(0);
                        log.info("Circuit breaker [{}] transitioning to HALF_OPEN", name);
                    }
                    return true;
                }
                return false;

            case HALF_OPEN:
                return halfOpenCalls.get() < halfOpenMaxCalls;

            default:
                return false;
        }
    }

    /**
     * Record a successful call. Call this after a successful HTTP request.
     */
    public void recordSuccess() {
        State currentState = state.get();

        if (currentState == State.HALF_OPEN) {
            if (state.compareAndSet(State.HALF_OPEN, State.CLOSED)) {
                failureCount.set(0);
                log.info("Circuit breaker [{}] recovered, transitioning to CLOSED", name);
            }
        } else if (currentState == State.CLOSED) {
            failureCount.set(0);
        }
    }

    /**
     * Record a failed call. Call this after a failed HTTP request
     * (timeout, exception, or non-retryable error).
     */
    public void recordFailure(Exception e) {
        failureCount.incrementAndGet();
        lastFailureTime.set(System.currentTimeMillis());

        State currentState = state.get();

        if (currentState == State.HALF_OPEN) {
            state.set(State.OPEN);
            log.warn("Circuit breaker [{}] reopened after failure in HALF_OPEN: {}",
                    name, e != null ? e.getMessage() : "null");
        } else if (currentState == State.CLOSED) {
            if (failureCount.get() >= failureThreshold) {
                state.set(State.OPEN);
                log.warn("Circuit breaker [{}] tripped after {} failures",
                        name, failureCount.get());
            }
        }
    }

    public State getState() {
        return state.get();
    }

    public int getFailureCount() {
        return failureCount.get();
    }

    public String getName() {
        return name;
    }

    public void reset() {
        state.set(State.CLOSED);
        failureCount.set(0);
        halfOpenCalls.set(0);
        log.info("Circuit breaker [{}] has been manually reset", name);
    }
}
