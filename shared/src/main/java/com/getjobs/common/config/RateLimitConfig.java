package com.getjobs.common.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * Configuration properties for rate limiting.
 * Prevents IP blocking by controlling request rates.
 */
@Data
@Configuration
@ConfigurationProperties(prefix = "app.rate-limit")
public class RateLimitConfig {

    private int maxRequestsPerMinute = 60;
    private int maxJobsPerMinute = 30;
    private int maxApiCallsPerMinute = 120;

    public int getMaxRequestsPerSecond() {
        return maxRequestsPerMinute / 60;
    }
}
