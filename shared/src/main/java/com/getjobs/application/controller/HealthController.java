package com.getjobs.application.controller;

import com.getjobs.common.cache.ThreadSafeCache;
import com.getjobs.worker.manager.PlaywrightManager;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.sql.DataSource;
import java.sql.Connection;
import java.time.Duration;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Properties;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Enhanced Health Check Controller with detailed system status.
 * Provides health endpoints for monitoring and alerting systems.
 */
@Slf4j
@RestController
@RequestMapping("/api")
public class HealthController {

    @Autowired
    private PlaywrightManager playwrightManager;

    @Autowired(required = false)
    private DataSource dataSource;

    private static final ThreadSafeCache<String, Object> healthCache =
            ThreadSafeCache.of("health-check", Duration.ofSeconds(30));

    private final AtomicBoolean isHealthy = new AtomicBoolean(true);

    /**
     * Basic health check endpoint
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        return ResponseEntity.ok(Map.of(
            "status", "UP",
            "service", "get-jobs",
            "timestamp", System.currentTimeMillis()
        ));
    }

    /**
     * Detailed health check with component status
     */
    @GetMapping("/health/detailed")
    public ResponseEntity<Map<String, Object>> detailedHealth() {
        @SuppressWarnings("unchecked")
        Map<String, Object> result = (Map<String, Object>) healthCache.getOrCompute("detailed",
                Duration.ofSeconds(10), this::performDetailedHealthCheck);

        if ("DOWN".equals(result.get("status"))) {
            return ResponseEntity.status(503).body(result);
        }

        return ResponseEntity.ok(result);
    }

    private Map<String, Object> performDetailedHealthCheck() {
        Map<String, Object> health = new LinkedHashMap<>();
        Instant start = Instant.now();

        health.put("status", "UP");
        health.put("service", "get-jobs");
        health.put("timestamp", System.currentTimeMillis());
        health.put("uptime", getUptime());

        // Component health checks
        Map<String, Object> components = new LinkedHashMap<>();

        // Database health
        components.put("database", checkDatabaseHealth());

        // Playwright health
        components.put("playwright", checkPlaywrightHealth());

        // Memory health
        components.put("memory", checkMemoryHealth());

        // Disk health
        components.put("disk", checkDiskHealth());

        health.put("components", components);

        // Check if any component is unhealthy
        boolean anyDown = components.values().stream()
                .filter(v -> v instanceof Map)
                .map(v -> (Map<?, ?>) v)
                .anyMatch(c -> !"UP".equals(c.get("status")));

        if (anyDown) {
            health.put("status", "DEGRADED");
            isHealthy.set(false);
        } else {
            health.put("status", "UP");
            isHealthy.set(true);
        }

        health.put("duration_ms", Duration.between(start, Instant.now()).toMillis());

        return health;
    }

    private Map<String, Object> checkDatabaseHealth() {
        Map<String, Object> db = new LinkedHashMap<>();

        if (dataSource == null) {
            db.put("status", "UNKNOWN");
            db.put("message", "DataSource not configured");
            return db;
        }

        long start = System.currentTimeMillis();
        try (Connection conn = dataSource.getConnection()) {
            boolean valid = conn.isValid(5);
            db.put("status", valid ? "UP" : "DOWN");
            db.put("response_time_ms", System.currentTimeMillis() - start);

            // Try to get connection pool stats if available
            try {
                Properties info = conn.getClientInfo();
                db.put("driver", info.getProperty("DriverName", "unknown"));
            } catch (Exception ignored) {}
        } catch (Exception e) {
            db.put("status", "DOWN");
            db.put("error", e.getMessage());
            log.warn("Database health check failed: {}", e.getMessage());
        }

        return db;
    }

    private Map<String, Object> checkPlaywrightHealth() {
        Map<String, Object> pw = new LinkedHashMap<>();

        try {
            boolean available = playwrightManager != null && playwrightManager.isBrowserAvailable();
            pw.put("status", available ? "UP" : "DOWN");
            pw.put("browser_available", available);
        } catch (Exception e) {
            pw.put("status", "DOWN");
            pw.put("error", e.getMessage());
            log.warn("Playwright health check failed: {}", e.getMessage());
        }

        return pw;
    }

    private Map<String, Object> checkMemoryHealth() {
        Map<String, Object> mem = new LinkedHashMap<>();

        Runtime rt = Runtime.getRuntime();
        long total = rt.maxMemory();
        long free = rt.freeMemory();
        long used = total - free;

        double usagePercent = (double) used / total * 100;

        mem.put("status", usagePercent > 90 ? "DEGRADED" : "UP");
        mem.put("total_mb", total / 1024 / 1024);
        mem.put("used_mb", used / 1024 / 1024);
        mem.put("free_mb", free / 1024 / 1024);
        mem.put("usage_percent", String.format("%.1f", usagePercent));

        return mem;
    }

    private Map<String, Object> checkDiskHealth() {
        Map<String, Object> disk = new LinkedHashMap<>();

        try {
            java.io.File root = java.io.File.listRoots()[0];
            long total = root.getTotalSpace();
            long free = root.getFreeSpace();
            long usable = root.getUsableSpace();

            double usagePercent = (double) (total - usable) / total * 100;

            disk.put("status", usagePercent > 95 ? "DEGRADED" : "UP");
            disk.put("total_gb", String.format("%.1f", total / 1024.0 / 1024 / 1024));
            disk.put("free_gb", String.format("%.1f", free / 1024.0 / 1024 / 1024));
            disk.put("usage_percent", String.format("%.1f", usagePercent));
        } catch (Exception e) {
            disk.put("status", "UNKNOWN");
            disk.put("error", e.getMessage());
        }

        return disk;
    }

    private String getUptime() {
        long startTime = getApplicationStartTime();
        long uptime = System.currentTimeMillis() - startTime;
        long seconds = uptime / 1000;
        long minutes = seconds / 60;
        long hours = minutes / 60;
        long days = hours / 24;

        return String.format("%dd %dh %dm %ds", days, hours % 24, minutes % 60, seconds % 60);
    }

    private static long applicationStartTime = System.currentTimeMillis();

    private static long getApplicationStartTime() {
        return applicationStartTime;
    }

    /**
     * Liveness probe - indicates if the application is running
     */
    @GetMapping("/health/live")
    public ResponseEntity<Map<String, Object>> liveness() {
        return ResponseEntity.ok(Map.of(
            "status", "UP",
            "timestamp", System.currentTimeMillis()
        ));
    }

    /**
     * Readiness probe - indicates if the application is ready to receive traffic
     */
    @GetMapping("/health/ready")
    public ResponseEntity<Map<String, Object>> readiness() {
        Map<String, Object> readiness = new LinkedHashMap<>();
        readiness.put("timestamp", System.currentTimeMillis());

        boolean ready = isHealthy.get();

        // Check if Playwright is available (required for job delivery)
        if (playwrightManager != null) {
            readiness.put("playwright_ready", playwrightManager.isBrowserAvailable());
            ready = ready && playwrightManager.isBrowserAvailable();
        }

        // Check database connectivity
        if (dataSource != null) {
            try (Connection conn = dataSource.getConnection()) {
                readiness.put("database_ready", conn.isValid(5));
                ready = ready && conn.isValid(5);
            } catch (Exception e) {
                readiness.put("database_ready", false);
                ready = false;
            }
        }

        readiness.put("status", ready ? "UP" : "DOWN");

        if (ready) {
            return ResponseEntity.ok(readiness);
        } else {
            return ResponseEntity.status(503).body(readiness);
        }
    }

    /**
     * Prometheus-compatible metrics endpoint
     */
    @GetMapping("/metrics/prometheus")
    public ResponseEntity<String> prometheusMetrics() {
        StringBuilder sb = new StringBuilder();

        // JVM metrics
        Runtime rt = Runtime.getRuntime();
        sb.append("# HELP jvm_memory_used_bytes JVM memory used bytes\n");
        sb.append("# TYPE jvm_memory_used_bytes gauge\n");
        sb.append(String.format("jvm_memory_used_bytes{type=\"heap\"} %d\n", rt.totalMemory() - rt.freeMemory()));
        sb.append(String.format("jvm_memory_used_bytes{type=\"nonheap\"} %d\n", rt.totalMemory()));

        sb.append("# HELP jvm_memory_max_bytes JVM memory max bytes\n");
        sb.append("# TYPE jvm_memory_max_bytes gauge\n");
        sb.append(String.format("jvm_memory_max_bytes{type=\"heap\"} %d\n", rt.maxMemory()));

        // Thread metrics
        Thread[] threads = new Thread[Thread.activeCount()];
        int activeThreads = Thread.enumerate(threads);
        sb.append("# HELP jvm_threads_current JVM threads current\n");
        sb.append("# TYPE jvm_threads_current gauge\n");
        sb.append(String.format("jvm_threads_current %d\n", activeThreads));

        // Application status
        sb.append("# HELP app_health_status Application health status\n");
        sb.append("# TYPE app_health_status gauge\n");
        sb.append(String.format("app_health_status %d\n", isHealthy.get() ? 1 : 0));

        // Playwright status
        if (playwrightManager != null) {
            sb.append("# HELP app_playwright_available Playwright browser availability\n");
            sb.append("# TYPE app_playwright_available gauge\n");
            sb.append(String.format("app_playwright_available %d\n",
                    playwrightManager.isBrowserAvailable() ? 1 : 0));
        }

        return ResponseEntity.ok()
                .header("Content-Type", "text/plain; version=0.0.4")
                .body(sb.toString());
    }
}
