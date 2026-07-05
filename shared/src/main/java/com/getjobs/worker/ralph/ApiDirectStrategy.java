package com.getjobs.worker.ralph;

import com.getjobs.common.http.ResilientHttpClient;
import com.getjobs.common.logging.StructuredLogger;
import com.getjobs.common.util.CircuitBreaker;
import com.getjobs.common.util.RateLimiter;
import com.microsoft.playwright.Page;
import com.microsoft.playwright.Locator;
import com.microsoft.playwright.options.Cookie;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Optional;
import java.util.Set;

/**
 * 策略3: API直投 (Enhanced with resilience patterns)
 * 绕过浏览器直接调用智联投递接口
 * 最后兜底手段
 * 
 * Security & Resilience improvements:
 * - Circuit breaker for API failures
 * - Rate limiting to prevent IP blocking
 * - Request timeout configuration
 * - Structured logging with sensitive data redaction
 */
@Slf4j
@Component
public class ApiDirectStrategy implements DeliveryStrategy {

    // Shared HTTP client with timeouts
    private static final HttpClient HTTP_CLIENT = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    // Circuit breaker for API resilience
    private static final CircuitBreaker circuitBreaker = CircuitBreaker.of("zhaopin-api");

    // Rate limiter to prevent IP blocking
    private static final RateLimiter rateLimiter = RateLimiter.forJobs(30); // 30 applications per minute

    @Override
    public String name() {
        return "api_direct";
    }

    @Override
    public int priority() {
        return 3;
    }

    @Override
    public boolean canHandle(RalphFailureDiagnosis diagnosis) {
        return true; // 最终兜底策略
    }

    @Override
    public DeliveryResult deliverWithCard(Page page, Locator card, String jobKey) {
        try {
            Locator linkEl = card.locator("a[href]");
            if (linkEl.count() == 0) {
                return deliver(page, jobKey, null);
            }
            String href = linkEl.first().getAttribute("href");
            return deliver(page, jobKey, href);
        } catch (Exception e) {
            return deliver(page, jobKey, null);
        }
    }

    @Override
    public DeliveryResult deliver(Page page, String jobKey, String jobLink) {
        StructuredLogger.RequestLogger requestLogger = StructuredLogger.startRequest("api_delivery");

        try {
            // Check rate limit
            if (!rateLimiter.tryAcquire()) {
                requestLogger.addContext("error", "rate_limit_exceeded");
                requestLogger.logFailure(new RuntimeException("Rate limit exceeded"));
                return DeliveryResult.failed("rate_limited", "请求过于频繁，请稍后再试");
            }

            // Check circuit breaker
            if (!circuitBreaker.isCallPermitted()) {
                requestLogger.addContext("error", "circuit_breaker_open");
                requestLogger.logFailure(new RuntimeException("Circuit breaker is open"));
                return DeliveryResult.failed("circuit_breaker", "服务暂时不可用，请稍后重试");
            }

            String jobId = extractJobId(jobLink);
            if (jobId == null || jobId.isBlank()) {
                return DeliveryResult.failed("job_id_missing", "无法从链接提取 jobId");
            }

            // 从 Playwright context 获取认证信息
            String cookies = extractCookies(page);
            String userAgent = extractUserAgent(page);

            if (cookies == null || cookies.isBlank()) {
                return DeliveryResult.failed("no_auth", "无法获取登录态 Cookie");
            }

            requestLogger.addContext("job_id", jobId);
            requestLogger.addContext("strategy", "api_direct");

            // Execute API delivery with resilience
            DeliveryResult result = attemptApiDeliveryWithResilience(jobId, cookies, userAgent);

            if (result.isSuccess()) {
                requestLogger.logSuccess();
            } else {
                requestLogger.addContext("error_type", result.getErrorType());
                requestLogger.addContext("error_message", result.getMessage());
                requestLogger.logSuccess(); // Still log as completed, just with failure status
            }

            return result;

        } catch (Exception e) {
            requestLogger.logFailure(e);
            return DeliveryResult.failed("api_exception", e.getMessage());
        }
    }

    private DeliveryResult attemptApiDeliveryWithResilience(String jobId, String cookies, String userAgent) {
        try {
            String apiUrl = "https://ihr.zhaopin.com/Pt/deliver/addDeliverResume.do";
            String body = "jk=" + jobId + "&needAddResume=0&addResumeVersion=1";

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(apiUrl))
                    .header("Content-Type", "application/x-www-form-urlencoded")
                    .header("Cookie", cookies)
                    .header("User-Agent", userAgent != null ? userAgent : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0")
                    .header("Referer", "https://www.zhaopin.com/")
                    .header("Accept", "application/json, text/plain, */*")
                    .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                    .timeout(Duration.ofSeconds(10))
                    .build();

            HttpResponse<String> response = HTTP_CLIENT.send(request, HttpResponse.BodyHandlers.ofString());

            int statusCode = response.statusCode();
            String responseBody = response.body();

            StructuredLogger.info("API delivery response",
                    "job_id", String.valueOf(jobId),
                    "status_code", String.valueOf(statusCode),
                    "response_length", String.valueOf(responseBody.length()));

            if (statusCode == 200 && responseBody.contains("true")) {
                log.info("API 直投成功: jobId={}", jobId);
                return DeliveryResult.success(name());
            }

            // Check for rate limiting (429) or server errors (5xx)
            if (statusCode == 429) {
                log.warn("API rate limited: jobId={}", jobId);
                return DeliveryResult.failed("rate_limited", "请求过于频繁 (HTTP 429)");
            }

            if (statusCode >= 500) {
                log.warn("API server error: status={}, body={}", statusCode, responseBody);
                return DeliveryResult.failed("api_server_error", "服务器错误 (HTTP " + statusCode + ")");
            }

            log.warn("API 直投失败: status={}, body={}", statusCode, responseBody);
            return DeliveryResult.failed("api_error", "HTTP " + statusCode + ": " + responseBody);

        } catch (java.net.SocketTimeoutException e) {
            log.error("API timeout for jobId={}", jobId, e);
            return DeliveryResult.failed("api_timeout", "请求超时，请检查网络连接");
        } catch (java.io.IOException e) {
            log.error("API network error for jobId={}", jobId, e);
            return DeliveryResult.failed("api_network_error", "网络错误: " + e.getMessage());
        } catch (Exception e) {
            log.error("API delivery exception for jobId={}", jobId, e);
            return DeliveryResult.failed("api_exception", e.getMessage());
        }
    }

    private String extractJobId(String jobLink) {
        if (jobLink == null || jobLink.isBlank()) return null;
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("/i(\\d+)\\.htm").matcher(jobLink);
        return m.find() ? m.group(1) : null;
    }

    private static final Set<String> SAFE_COOKIE_NAMES = Set.of(
            "zpsc", "urlhistory", "s", "adsid", "gsid", "cna"
    );

    private static final Set<String> SENSITIVE_COOKIE_PATTERNS = Set.of(
            "session", "auth", "token", "login", "sso", "cas", "shiro"
    );

    private String extractCookies(Page page) {
        try {
            List<Cookie> cookieList = page.context().cookies();
            if (cookieList == null || cookieList.isEmpty()) return "";
            StringBuilder sb = new StringBuilder();
            int included = 0;
            int skipped = 0;
            for (Cookie c : cookieList) {
                String name = c.name;
                if (isSensitiveCookie(name)) {
                    skipped++;
                    continue;
                }
                if (sb.length() > 0) sb.append("; ");
                sb.append(name).append("=").append(c.value);
                included++;
            }
            if (skipped > 0) {
                log.debug("Skipped {} sensitive cookies, included {} safe cookies", skipped, included);
            }
            return sb.toString();
        } catch (Exception e) {
            log.warn("提取 Cookie 失败: {}", e.getMessage());
            return "";
        }
    }

    private boolean isSensitiveCookie(String cookieName) {
        if (cookieName == null) return true;
        String lower = cookieName.toLowerCase();
        for (String pattern : SENSITIVE_COOKIE_PATTERNS) {
            if (lower.contains(pattern)) return true;
        }
        return false;
    }

    private String extractUserAgent(Page page) {
        try {
            return page.evaluate("navigator.userAgent").toString();
        } catch (Exception e) {
            return null;
        }
    }
}
