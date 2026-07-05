package com.getjobs.worker.manager;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.getjobs.application.entity.CookieEntity;
import com.getjobs.application.service.CookieService;
import com.getjobs.common.logging.StructuredLogger;
import com.getjobs.worker.utils.PlaywrightUtil;
import com.microsoft.playwright.*;
import com.microsoft.playwright.options.Cookie;
import com.microsoft.playwright.options.LoadState;
import com.microsoft.playwright.options.WaitUntilState;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.event.ContextClosedEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Centralized Playwright browser manager with graceful shutdown and resource cleanup.
 * Ensures proper browser lifecycle management and prevents resource leaks.
 */
@Slf4j
@Component
public class PlaywrightManager {

    private static final int ZHI_LIAN_CDP_PORT = 7868;

    private Playwright playwright;
    private Browser zhilianBrowser;
    private BrowserContext zhilianContext;
    private Page zhilianPage;

    private volatile boolean initialized = false;
    private volatile boolean initFailed = false;
    private volatile boolean shuttingDown = false;
    private final Object initLock = new Object();
    private volatile boolean zhilianLoggedIn = false;
    private final AtomicInteger totalNavigations = new AtomicInteger(0);
    private final AtomicInteger totalErrors = new AtomicInteger(0);
    private final AtomicBoolean cleanupRegistered = new AtomicBoolean(false);

    @Autowired
    private CookieService cookieService;

    private static final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * Initialize on application startup
     */
    @PostConstruct
    public void postConstruct() {
        StructuredLogger.info("PlaywrightManager initializing",
                "component", "PlaywrightManager",
                "event", "startup");
    }

    /**
     * Register shutdown hook for graceful termination
     */
    @EventListener(ContextClosedEvent.class)
    public void onApplicationShutdown(ContextClosedEvent event) {
        log.info("Received shutdown signal, initiating graceful Playwright shutdown...");
        shutdown();
    }

    /**
     * JVM shutdown hook as backup
     */
    private void registerShutdownHook() {
        if (cleanupRegistered.compareAndSet(false, true)) {
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                log.info("JVM shutdown hook triggered for PlaywrightManager");
                shutdown();
            }, "PlaywrightManager-ShutdownHook"));
        }
    }

    private void ensureInitialized() {
        if (initialized) return;
        if (initFailed) return;
        if (shuttingDown) return;

        // Register shutdown hook on first use
        registerShutdownHook();

        synchronized (initLock) {
            if (initialized) return;
            if (initFailed) return;
            if (shuttingDown) return;

            try {
                playwright = Playwright.create();
                StructuredLogger.info("Playwright engine started",
                        "component", "PlaywrightManager",
                        "event", "engine_started");

                boolean headless = Boolean.parseBoolean(System.getenv().getOrDefault("PLAYWRIGHT_HEADLESS", "false"));

                zhilianBrowser = playwright.chromium().launch(new BrowserType.LaunchOptions()
                        .setHeadless(headless)
                        .setArgs(List.of(
                                "--remote-debugging-port=" + ZHI_LIAN_CDP_PORT,
                                "--start-maximized",
                                "--no-sandbox",
                                "--disable-setuid-sandbox",
                                "--disable-dev-shm-usage"
                        )));

                zhilianContext = zhilianBrowser.newContext(new Browser.NewContextOptions()
                        .setViewportSize(1920, 1080)
                        .setUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"));

                zhilianPage = zhilianContext.newPage();
                zhilianPage.setDefaultTimeout(30000);

                // Add error handler for page errors
                zhilianPage.onPageError(pageError -> {
                    totalErrors.incrementAndGet();
                    log.warn("Page error: {}", pageError);
                });

                log.info("智联招聘浏览器已初始化");
                StructuredLogger.info("Browser initialized",
                        "component", "PlaywrightManager",
                        "event", "browser_initialized",
                        "headless", String.valueOf(headless));
                initialized = true;
            } catch (Exception e) {
                log.error("Playwright Manager 初始化失败: {}, 请运行 'npx playwright install chromium' 安装浏览器", e.getMessage());
                StructuredLogger.error("Browser initialization failed",
                        e,
                        "component", "PlaywrightManager",
                        "error_type", e.getClass().getSimpleName());
                // 不抛出异常，让应用继续运行（懒加载）
                initFailed = true;
                try {
                    java.nio.file.Files.writeString(
                        java.nio.file.Paths.get("target/playwright-init-error.txt"),
                        java.time.LocalDateTime.now() + " - PlaywrightManager init failed: " + e + "\n",
                        java.nio.file.StandardOpenOption.CREATE, java.nio.file.StandardOpenOption.APPEND
                    );
                } catch (Exception ex) {}
            }
        }
    }

    /**
     * Graceful shutdown of all Playwright resources
     */
    @PreDestroy
    public void shutdown() {
        if (shuttingDown) {
            log.debug("Playwright shutdown already in progress");
            return;
        }

        shuttingDown = true;
        StructuredLogger.info("Initiating Playwright shutdown",
                "component", "PlaywrightManager",
                "event", "shutdown_initiated",
                "total_navigations", String.valueOf(totalNavigations.get()),
                "total_errors", String.valueOf(totalErrors.get()));

        long startTime = System.currentTimeMillis();

        // Save cookies before shutdown if possible
        if (initialized && zhilianContext != null) {
            try {
                saveZhilianCookiesToDb("graceful_shutdown");
                StructuredLogger.info("Cookies saved before shutdown");
            } catch (Exception e) {
                log.warn("Failed to save cookies during shutdown: {}", e.getMessage());
            }
        }

        // Close resources in reverse order of creation
        try {
            if (zhilianPage != null) {
                zhilianPage.close();
                log.debug("Page closed");
            }
        } catch (Exception e) {
            log.warn("Error closing page: {}", e.getMessage());
        }

        try {
            if (zhilianContext != null) {
                zhilianContext.close();
                log.debug("Context closed");
            }
        } catch (Exception e) {
            log.warn("Error closing context: {}", e.getMessage());
        }

        try {
            if (zhilianBrowser != null) {
                zhilianBrowser.close();
                log.debug("Browser closed");
            }
        } catch (Exception e) {
            log.warn("Error closing browser: {}", e.getMessage());
        }

        try {
            if (playwright != null) {
                playwright.close();
                log.debug("Playwright engine closed");
            }
        } catch (Exception e) {
            log.warn("Error closing Playwright: {}", e.getMessage());
        }

        long duration = System.currentTimeMillis() - startTime;
        StructuredLogger.info("Playwright shutdown completed",
                "component", "PlaywrightManager",
                "event", "shutdown_completed",
                "duration_ms", String.valueOf(duration));

        log.info("Playwright Manager 已关闭 (耗时: {}ms)", duration);
    }

    public boolean isBrowserAvailable() {
        return initialized && zhilianPage != null;
    }

    public void refreshLoginStatus(String platform) {
        if ("zhilian".equals(platform)) {
            try {
                CookieEntity cookie = cookieService.getCookieByPlatform("zhilian");
                zhilianLoggedIn = cookie != null && cookie.getCookieValue() != null && !cookie.getCookieValue().isBlank();
            } catch (Exception e) {
                zhilianLoggedIn = false;
            }
        }
    }

    public boolean isLoggedIn(String platform) {
        if ("zhilian".equals(platform)) {
            // 如果内存里的状态还没设置,通过检测浏览器 cookies 推断
            if (!zhilianLoggedIn && zhilianContext != null) {
                try {
                    List<Cookie> cookies = zhilianContext.cookies();
                    for (Cookie c : cookies) {
                        String n = c.name == null ? "" : c.name.toLowerCase();
                        if ((n.contains("zp_token") || n.contains("login_token") || n.contains("at"))
                                && c.value != null && c.value.length() > 10) {
                            zhilianLoggedIn = true;
                            break;
                        }
                    }
                } catch (Exception ignore) { }
            }
            return zhilianLoggedIn;
        }
        return false;
    }

    public void setLoginStatus(String platform, boolean loggedIn) {
        if ("zhilian".equals(platform)) {
            this.zhilianLoggedIn = loggedIn;
            log.info("智联登录状态更新: {}", loggedIn);
        }
    }

    public String getZhilianAvatarUrl() {
        if (zhilianContext == null) return null;
        try {
            for (Cookie c : zhilianContext.cookies()) {
                if ("ZP_USER_AVATAR".equalsIgnoreCase(c.name) || "avatar".equalsIgnoreCase(c.name)) {
                    return c.value;
                }
            }
        } catch (Exception ignore) { }
        return null;
    }

    public void reloadCookiesFromDatabase(String platform) {
        if (!initialized) return;
        try {
            if ("zhilian".equals(platform)) {
                CookieEntity cookie = cookieService.getCookieByPlatform("zhilian");
                if (cookie != null && cookie.getCookieValue() != null) {
                    List<Cookie> cookies = parseCookies(cookie.getCookieValue());
                    zhilianContext.addCookies(cookies);
                }
            }
        } catch (Exception e) {
            log.warn("重新加载 Cookie 失败: {}", e.getMessage());
        }
    }

    public void saveZhilianCookiesToDb(String remark) {
        if (!initialized) return;
        try {
            List<Cookie> cookies = zhilianContext.cookies();
            String json = objectMapper.writeValueAsString(cookies);
            cookieService.saveOrUpdateCookie("zhilian", json, remark);
        } catch (Exception e) {
            log.error("保存智联 Cookie 失败", e);
        }
    }

    public void clearZhilianCookies() {
        if (!initialized) return;
        try {
            zhilianContext.clearCookies();
        } catch (Exception e) {
            log.warn("清理智联 Cookie 失败", e);
        }
    }

    public void triggerZhilianLogin() {
        ensureInitialized();
        if (zhilianPage == null) return;
        try {
            // 1. 打开智联首页
            zhilianPage.navigate("https://www.zhaopin.com/", new Page.NavigateOptions()
                    .setTimeout(60000)
                    .setWaitUntil(WaitUntilState.DOMCONTENTLOADED));
            PlaywrightUtil.sleep(2);

            // 2. 尝试点击登录按钮（多种常见 selector）
            boolean clicked = false;
            String[] loginSelectors = {
                    "text=登录",
                    "a:has-text('登录')",
                    "button:has-text('登录')",
                    "[class*='login-btn']",
                    "[class*='header-login']",
                    ".login-entry",
                    "[data-login]"
            };
            for (String selector : loginSelectors) {
                try {
                    Locator btn = zhilianPage.locator(selector).first();
                    if (btn != null && btn.count() > 0 && btn.isVisible()) {
                        btn.click(new Locator.ClickOptions().setTimeout(3000));
                        clicked = true;
                        log.info("已点击登录入口: {}", selector);
                        break;
                    }
                } catch (Exception ignore) {
                    // 继续尝试下一个
                }
            }
            if (!clicked) {
                log.warn("未找到登录入口,请在弹出的浏览器里手动操作");
            }

            // 3. 等待二维码出现（最多 15 秒）
            boolean qrShown = false;
            for (int i = 0; i < 15; i++) {
                try {
                    // 智联二维码常见 class
                    if (zhilianPage.locator(".login-type__qrcode, .qrcode-box, [class*='qrcode'], canvas").count() > 0
                            || zhilianPage.url().contains("/login")
                            || zhilianPage.url().contains("passport")) {
                        qrShown = true;
                        break;
                    }
                } catch (Exception ignore) { }
                PlaywrightUtil.sleep(1);
            }
            log.info("智联登录入口触发完成, QR显示={}", qrShown);

            // 4. 后台监控:二维码出现后,每隔 3 秒检查一次 cookies,
            //    发现登录成功的 cookies(zp_token / login_token / at 等)自动保存。
            monitorLoginAndSaveCookies();
        } catch (Exception e) {
            log.error("触发智联登录失败", e);
        }
    }

    /** 后台线程:轮询检查 cookies,登录成功时自动持久化 */
    private volatile boolean loginMonitorStarted = false;
    private void monitorLoginAndSaveCookies() {
        if (loginMonitorStarted) return;
        loginMonitorStarted = true;
        Thread t = new Thread(() -> {
            String[] loginCookieNames = {"zp_token", "login_token", "x-zp-at", "at", "userId", "user_id", "sess", "JSESSIONID"};
            for (int i = 0; i < 120; i++) { // 最多轮询 6 分钟
                try {
                    if (shuttingDown || zhilianContext == null) break;
                    List<Cookie> cookies = zhilianContext.cookies();
                    boolean loggedIn = false;
                    for (Cookie c : cookies) {
                        for (String name : loginCookieNames) {
                            if (c.name != null && c.name.toLowerCase().contains(name.toLowerCase())
                                    && c.value != null && c.value.length() > 10) {
                                loggedIn = true;
                                break;
                            }
                        }
                        if (loggedIn) break;
                    }
                    if (loggedIn) {
                        log.info("检测到登录 cookies,自动保存到数据库");
                        saveZhilianCookiesToDb("auto-saved-after-qr-scan");
                        zhilianLoggedIn = true;
                        setLoginStatus("zhilian", true);
                        break;
                    }
                } catch (Exception e) {
                    log.warn("登录监控异常: {}", e.getMessage());
                }
                PlaywrightUtil.sleep(3);
            }
            loginMonitorStarted = false;
        }, "Zhilian-LoginMonitor");
        t.setDaemon(true);
        t.start();
    }

    private List<Cookie> parseCookies(String cookieJson) {
        List<Cookie> cookies = new java.util.ArrayList<>();
        try {
            var node = objectMapper.readTree(cookieJson);
            if (node.isArray()) {
                for (var elem : node) {
                    Cookie c = new Cookie(elem.get("name").asText(), elem.get("value").asText());
                    if (elem.has("domain") && !elem.get("domain").isNull()) c.domain = elem.get("domain").asText();
                    if (elem.has("path") && !elem.get("path").isNull()) c.path = elem.get("path").asText();
                    if (elem.has("expires") && !elem.get("expires").isNull()) c.expires = elem.get("expires").asDouble();
                    cookies.add(c);
                }
            }
        } catch (Exception e) {
            log.error("解析 Cookie 失败", e);
        }
        return cookies;
    }

    public Page getZhilianPage() {
        ensureInitialized();
        return zhilianPage;
    }

    @PreDestroy
    public void destroy() {
        try {
            if (zhilianPage != null) zhilianPage.close();
            if (zhilianContext != null) zhilianContext.close();
            if (zhilianBrowser != null) zhilianBrowser.close();
            if (playwright != null) playwright.close();
        } catch (Exception e) {
            log.error("Playwright Manager 关闭失败", e);
        }
    }
}
