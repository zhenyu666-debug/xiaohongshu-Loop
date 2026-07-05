package com.getjobs.common.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * Configuration properties for HTTP client timeouts.
 * Provides centralized timeout management for external API calls.
 */
@Data
@Configuration
@ConfigurationProperties(prefix = "app.http")
public class HttpClientConfig {

    private int connectTimeoutSeconds = 10;
    private int readTimeoutSeconds = 30;
    private int writeTimeoutSeconds = 30;
    private int maxRetries = 3;
    private int retryBaseDelayMs = 1000;

    public java.time.Duration getConnectTimeout() {
        return java.time.Duration.ofSeconds(connectTimeoutSeconds);
    }

    public java.time.Duration getReadTimeout() {
        return java.time.Duration.ofSeconds(readTimeoutSeconds);
    }

    public java.time.Duration getWriteTimeout() {
        return java.time.Duration.ofSeconds(writeTimeoutSeconds);
    }
}
