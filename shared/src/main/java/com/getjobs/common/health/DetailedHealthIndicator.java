package com.getjobs.common.health;

import com.getjobs.application.repository.CookieRepository;
import com.getjobs.worker.manager.PlaywrightManager;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.stereotype.Component;

import javax.sql.DataSource;
import java.sql.Connection;
import java.time.Duration;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Detailed health endpoint for /actuator/health/detailed
 * Reports status of all major components: playwright, database, cookies
 */
@Component("detailedHealthIndicator")
@Slf4j
public class DetailedHealthIndicator implements HealthIndicator {

    @Autowired(required = false)
    private PlaywrightManager playwrightManager;

    @Autowired(required = false)
    private DataSource dataSource;

    @Autowired(required = false)
    private CookieRepository cookieRepository;

    private volatile Instant lastCheckTime = Instant.now();
    private volatile String lastStatus = "UNKNOWN";
    private volatile Map<String, Object> cachedResult = null;

    @Override
    public Health health() {
        return checkHealth();
    }

    public Health checkHealth() {
        Map<String, Object> details = getDetails();

        String overallStatus = (String) details.get("status");
        Health.Builder builder = switch (overallStatus) {
            case "UP" -> Health.up();
            case "DOWN" -> Health.down();
            case "DEGRADED" -> Health.unknown();
            default -> Health.unknown();
        };

        @SuppressWarnings("unchecked")
        Map<String, Object> components = (Map<String, Object>) details.get("components");
        if (components != null) {
            builder.withDetail("components", components);
        }
        builder.withDetail("uptime", details.get("uptime"));
        builder.withDetail("timestamp", details.get("timestamp"));

        return builder.build();
    }

    public Map<String, Object> getDetails() {
        if (cachedResult != null && Duration.between(lastCheckTime, Instant.now()).toMillis() < 10000) {
            return cachedResult;
        }

        Map<String, Object> health = new LinkedHashMap<>();
        Instant start = Instant.now();

        health.put("service", "get-jobs");
        health.put("timestamp", System.currentTimeMillis());
        health.put("uptime", getUptime());

        Map<String, Object> components = new LinkedHashMap<>();

        // Database health
        components.put("database", checkDatabaseHealth());

        // Playwright health
        components.put("playwright", checkPlaywrightHealth());

        // Cookie health
        components.put("cookies", checkCookieHealth());

        // Memory health
        components.put("memory", checkMemoryHealth());

        health.put("components", components);

        // Determine overall status
        boolean anyDown = components.values().stream()
                .filter(v -> v instanceof Map)
                .map(v -> (Map<?, ?>) v)
                .anyMatch(c -> "DOWN".equals(c.get("status")));

        boolean anyDegraded = components.values().stream()
                .filter(v -> v instanceof Map)
                .map(v -> (Map<?, ?>) v)
                .anyMatch(c -> "DEGRADED".equals(c.get("status")));

        if (anyDown) {
            health.put("status", "DOWN");
            lastStatus = "DOWN";
        } else if (anyDegraded) {
            health.put("status", "DEGRADED");
            lastStatus = "DEGRADED";
        } else {
            health.put("status", "UP");
            lastStatus = "UP";
        }

        health.put("check_duration_ms", Duration.between(start, Instant.now()).toMillis());

        cachedResult = health;
        lastCheckTime = Instant.now();

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

            if (valid) {
                try {
                    var metaData = conn.getMetaData();
                    db.put("database_product", metaData.getDatabaseProductName());
                    db.put("database_version", metaData.getDatabaseProductVersion());
                } catch (Exception ignored) {}
            }
        } catch (Exception e) {
            db.put("status", "DOWN");
            db.put("error", e.getMessage());
            log.warn("Database health check failed: {}", e.getMessage());
        }

        return db;
    }

    private Map<String, Object> checkPlaywrightHealth() {
        Map<String, Object> pw = new LinkedHashMap<>();

        if (playwrightManager == null) {
            pw.put("status", "UNKNOWN");
            pw.put("message", "PlaywrightManager not configured");
            return pw;
        }

        try {
            boolean available = playwrightManager.isBrowserAvailable();
            pw.put("status", available ? "UP" : "DOWN");
            pw.put("browser_available", available);

            if (!available) {
                pw.put("message", "Browser not available - may need restart");
            }
        } catch (Exception e) {
            pw.put("status", "DOWN");
            pw.put("error", e.getMessage());
            log.warn("Playwright health check failed: {}", e.getMessage());
        }

        return pw;
    }

    private Map<String, Object> checkCookieHealth() {
        Map<String, Object> cookies = new LinkedHashMap<>();

        if (cookieRepository == null) {
            cookies.put("status", "UNKNOWN");
            cookies.put("message", "CookieRepository not configured");
            return cookies;
        }

        try {
            long totalCookies = cookieRepository.count();
            long freshCookies = cookieRepository.findAll().stream()
                    .filter(c -> c.getUpdatedAt() != null)
                    .count();

            cookies.put("status", "UP");
            cookies.put("total_cookies", totalCookies);
            cookies.put("valid_cookies", freshCookies);
            cookies.put("expired_cookies", totalCookies - freshCookies);

            if (freshCookies == 0) {
                cookies.put("status", "DEGRADED");
                cookies.put("message", "No valid cookies - may need to re-login");
            }
        } catch (Exception e) {
            cookies.put("status", "DOWN");
            cookies.put("error", e.getMessage());
            log.warn("Cookie health check failed: {}", e.getMessage());
        }

        return cookies;
    }

    private Map<String, Object> checkMemoryHealth() {
        Map<String, Object> mem = new LinkedHashMap<>();

        Runtime rt = Runtime.getRuntime();
        long total = rt.maxMemory();
        long free = rt.freeMemory();
        long used = total - free;

        double usagePercent = (double) used / total * 100;

        String status;
        if (usagePercent > 90) {
            status = "DOWN";
        } else if (usagePercent > 75) {
            status = "DEGRADED";
        } else {
            status = "UP";
        }

        mem.put("status", status);
        mem.put("total_mb", total / 1024 / 1024);
        mem.put("used_mb", used / 1024 / 1024);
        mem.put("free_mb", free / 1024 / 1024);
        mem.put("usage_percent", String.format("%.1f", usagePercent));

        return mem;
    }

    private String getUptime() {
        return formatDuration(System.currentTimeMillis() - getApplicationStartTime());
    }

    private static long applicationStartTime = System.currentTimeMillis();

    private static long getApplicationStartTime() {
        return applicationStartTime;
    }

    private static String formatDuration(long millis) {
        long seconds = millis / 1000;
        long minutes = seconds / 60;
        long hours = minutes / 60;
        long days = hours / 24;

        return String.format("%dd %dh %dm %ds", days, hours % 24, minutes % 60, seconds % 60);
    }
}
