package com.getjobs.common.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.util.StringUtils;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.Arrays;
import java.util.List;
import java.util.concurrent.Executor;
import java.util.concurrent.ThreadPoolExecutor;

/**
 * Application configuration for resilience and thread management.
 */
@Configuration
@EnableScheduling
@EnableConfigurationProperties
public class AppConfig {

    @Value("${app.cors.allowed-origins:}")
    private String allowedOrigins;

    @Value("${app.cors.max-age-seconds:3600}")
    private int corsMaxAgeSeconds;

    @Bean(name = "taskExecutor")
    public Executor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(4);
        executor.setMaxPoolSize(8);
        executor.setQueueCapacity(100);
        executor.setThreadNamePrefix("getjobs-");
        executor.setKeepAliveSeconds(60);
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.setAwaitTerminationSeconds(30);
        executor.initialize();
        return executor;
    }

    @Bean
    public WebMvcConfigurer corsConfigurer() {
        return new WebMvcConfigurer() {
            @Override
            public void addCorsMappings(CorsRegistry registry) {
                if (StringUtils.hasText(allowedOrigins)) {
                    List<String> origins = Arrays.asList(allowedOrigins.split(","));
                    registry.addMapping("/api/**")
                            .allowedOrigins(origins.toArray(new String[0]))
                            .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                            .allowedHeaders("*")
                            .allowCredentials(true)
                            .maxAge(corsMaxAgeSeconds);
                } else {
                    registry.addMapping("/api/**")
                            .maxAge(corsMaxAgeSeconds);
                }
            }
        };
    }
}
