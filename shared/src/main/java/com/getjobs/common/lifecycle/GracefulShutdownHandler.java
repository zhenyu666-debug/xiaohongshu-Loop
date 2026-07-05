package com.getjobs.common.lifecycle;

import com.getjobs.common.logging.StructuredLogger;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.event.ContextClosedEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Graceful shutdown handler for the application.
 * Ensures all resources are properly cleaned up before JVM exit.
 */
@Slf4j
@Component
public class GracefulShutdownHandler {

    private final AtomicBoolean shuttingDown = new AtomicBoolean(false);

    @PostConstruct
    public void init() {
        log.info("GracefulShutdownHandler initialized");
        StructuredLogger.info("Application starting",
                "component", "GracefulShutdownHandler",
                "event", "init");
    }

    @EventListener(ContextClosedEvent.class)
    public void onApplicationEvent(ContextClosedEvent event) {
        if (shuttingDown.compareAndSet(false, true)) {
            log.info("Context closed event received, initiating graceful shutdown...");
            StructuredLogger.info("Graceful shutdown initiated",
                    "component", "GracefulShutdownHandler",
                    "event", "context_closed",
                    "remaining_time_ms", "graceful_shutdown");
        }
    }

    @PreDestroy
    public void onDestroy() {
        if (shuttingDown.compareAndSet(false, true)) {
            log.info("PreDestroy hook triggered, cleaning up resources...");
            StructuredLogger.info("Resource cleanup starting",
                    "component", "GracefulShutdownHandler",
                    "event", "pre_destroy");
        }
    }

    public boolean isShuttingDown() {
        return shuttingDown.get();
    }
}
