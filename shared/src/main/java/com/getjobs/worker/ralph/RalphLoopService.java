package com.getjobs.worker.ralph;

import com.getjobs.application.entity.TaskSession;
import com.getjobs.application.repository.TaskSessionRepository;
import com.microsoft.playwright.Page;
import com.microsoft.playwright.Locator;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Ralph Loop 核心服务
 * AI 自主循环：执行 -> 诊断 -> 自愈修复 -> 策略降级 -> 学习约束
 */
@Slf4j
@Service
public class RalphLoopService {

    private static final int DEFAULT_MAX_ATTEMPTS = 3;

    private final RalphGuardrailsManager guardrailsManager;
    private final RalphTaskQueue taskQueue;
    private final TaskSessionRepository taskSessionRepository;
    private final List<DeliveryStrategy> strategies;

    // 投递结果回调
    @FunctionalInterface
    public interface DeliveryCallback {
        void onResult(String jobKey, DeliveryResult result, String usedStrategy);
    }

    private DeliveryCallback callback;

    /** 指数退避基础时间（毫秒） */
    private static final long BASE_SLEEP_MS = 1000L;
    /** 验证码等待时间 */
    private static final long CAPTCHA_SLEEP_MS = 3000L;
    /** 最大退避倍数 */
    private static final int MAX_BACKOFF_MULTIPLIER = 4;

    public RalphLoopService(RalphGuardrailsManager guardrailsManager,
                           RalphTaskQueue taskQueue,
                           TaskSessionRepository taskSessionRepository,
                           List<DeliveryStrategy> strategies) {
        this.guardrailsManager = guardrailsManager;
        this.taskQueue = taskQueue;
        this.taskSessionRepository = taskSessionRepository;
        this.strategies = strategies;
    }

    public void setCallback(DeliveryCallback cb) {
        this.callback = cb;
    }

    // ===== 独立模式工厂方法（用于 ZhiLianRunner 等非 Spring 环境）=====
    public static RalphLoopService forStandalone(Page page, String platform, String keyword) {
        // 独立模式下使用内存 guardrails + 内存 taskQueue
        RalphGuardrailsManager gr = new RalphGuardrailsManager();
        RalphTaskQueue tq = new RalphTaskQueue();
        // 从文件加载已有数据
        gr.load();
        tq.load();

        // 创建 3 种策略
        List<DeliveryStrategy> strat = List.of(
                new HoverCardStrategy(),
                new DetailPageStrategy(),
                new ApiDirectStrategy()
        );

        return new RalphLoopService(gr, tq, null, strat);
    }

    /**
     * 独立模式：执行一次投递（无 TaskSession 持久化）
     */
    public DeliveryResult deliverSingle(Page page, String jobKey, String jobLink) {
        RalphFailureDiagnosis lastDiagnosis = null;

        for (int attempt = 1; attempt <= DEFAULT_MAX_ATTEMPTS; attempt++) {
            DeliveryStrategy strategy = selectStrategy(lastDiagnosis, attempt);
            log.debug("[Ralph] attempt={} strategy={}", attempt, strategy.name());

            DeliveryResult result = strategy.deliver(page, jobKey, jobLink);

            if (result.isSuccess() || result.getStatus() == DeliveryResult.Status.ALREADY_DELIVERED) {
                return result;
            }

            lastDiagnosis = diagnose(result, attempt);

            if (lastDiagnosis.isAutoFixable() && !lastDiagnosis.isKnownPitfall()) {
                if ("element_timeout".equals(lastDiagnosis.getPattern()) || "network_error".equals(lastDiagnosis.getPattern())) {
                    safeSleep(BASE_SLEEP_MS);
                }
                if ("captcha_detected".equals(lastDiagnosis.getPattern())) {
                    safeSleep(CAPTCHA_SLEEP_MS);
                }
                continue;
            }

            if (!lastDiagnosis.isKnownPitfall()) {
                guardrailsManager.learn(lastDiagnosis);
            }

            result.setDiagnosed(true);
            return result;
        }

        DeliveryResult finalResult = DeliveryResult.failed("max_attempts_reached",
                "达到最大重试次数: " + (lastDiagnosis != null ? lastDiagnosis.getPattern() : "unknown"));
        finalResult.setDiagnosed(true);
        return finalResult;
    }

    /**
     * 独立模式：使用已知 card locator 执行投递（避免重复搜索）
     */
    public DeliveryResult deliverWithCard(Page page, Locator card, String jobKey, String jobLink) {
        RalphFailureDiagnosis lastDiagnosis = null;

        for (int attempt = 1; attempt <= DEFAULT_MAX_ATTEMPTS; attempt++) {
            DeliveryStrategy strategy = selectStrategy(lastDiagnosis, attempt);
            log.debug("[Ralph] attempt={} strategy={} (card mode)", attempt, strategy.name());

            DeliveryResult result = strategy.deliverWithCard(page, card, jobKey);

            if (result.isSuccess() || result.getStatus() == DeliveryResult.Status.ALREADY_DELIVERED) {
                return result;
            }

            lastDiagnosis = diagnose(result, attempt);

            if (lastDiagnosis.isAutoFixable() && !lastDiagnosis.isKnownPitfall()) {
                if ("element_timeout".equals(lastDiagnosis.getPattern()) || "network_error".equals(lastDiagnosis.getPattern())) {
                    safeSleep(BASE_SLEEP_MS);
                }
                if ("captcha_detected".equals(lastDiagnosis.getPattern())) {
                    safeSleep(CAPTCHA_SLEEP_MS);
                }
                continue;
            }

            if (!lastDiagnosis.isKnownPitfall()) {
                guardrailsManager.learn(lastDiagnosis);
            }

            result.setDiagnosed(true);
            return result;
        }

        DeliveryResult finalResult = DeliveryResult.failed("max_attempts_reached",
                "达到最大重试次数: " + (lastDiagnosis != null ? lastDiagnosis.getPattern() : "unknown"));
        finalResult.setDiagnosed(true);
        return finalResult;
    }

    /**
     * 启动一个投递会话
     */
    public TaskSession startSession(String platform, String keyword, int totalJobs) {
        TaskSession session = new TaskSession();
        session.setSessionId(UUID.randomUUID().toString());
        session.setPlatform(platform);
        session.setKeyword(keyword);
        session.setTotalJobs(totalJobs);
        session.setStatus("RUNNING");
        session.setStartedAt(LocalDateTime.now());
        session.setCurrentStrategy(getDefaultStrategy().name());
        return taskSessionRepository.save(session);
    }

    /**
     * 使用 Ralph Loop 执行一次投递
     */
    public DeliveryResult executeDelivery(Page page, String jobKey, String jobLink, TaskSession session) {
        RalphFailureDiagnosis lastDiagnosis = null;

        for (int attempt = 1; attempt <= DEFAULT_MAX_ATTEMPTS; attempt++) {
            // 1. 检查 guardrails
            Optional<RalphGuardrail> matched = guardrailsManager.checkMatch("", "");
            if (matched.isPresent()) {
                RalphGuardrail g = matched.get();
                log.info("[Ralph] Guardrail 命中: {} -> {}", g.getPattern(), g.getAction());
                session.setGuardrailsTriggered(session.getGuardrailsTriggered() + 1);
                taskSessionRepository.save(session);

                // 根据 action 决定行为
                if ("skip".equals(g.getAction())) {
                    DeliveryResult r = DeliveryResult.blocked("guardrail: " + g.getPattern());
                    r.setDiagnosed(true);
                    onDeliveryResult(jobKey, r, "blocked_by_guardrail");
                    return r;
                }
            }

            // 2. 选择策略
            DeliveryStrategy strategy = selectStrategy(lastDiagnosis, attempt);
            String strategyName = strategy.name();
            log.debug("[Ralph] attempt={} strategy={}", attempt, strategyName);

            if (!strategyName.equals(session.getCurrentStrategy())) {
                session.setCurrentStrategy(strategyName);
                session.setStrategySwitches(session.getStrategySwitches() + 1);
                taskSessionRepository.save(session);
            }

            // 3. 执行投递
            DeliveryResult result = strategy.deliver(page, jobKey, jobLink);

            if (result.isSuccess() || result.getStatus() == DeliveryResult.Status.ALREADY_DELIVERED) {
                onDeliveryResult(jobKey, result, strategyName);
                return result;
            }

            // 4. 诊断失败原因
            lastDiagnosis = diagnose(result, attempt);
            lastDiagnosis.setDiagnosed(true);

            // 5. 检查是否已知的坑
            Optional<RalphGuardrail> pitfall = guardrailsManager.checkMatch(lastDiagnosis.getPattern(), lastDiagnosis.getDescription());
            if (pitfall.isPresent()) {
                RalphGuardrail g = pitfall.get();
                g.incrementHit();
                guardrailsManager.save();

                // 如果该陷阱已达阈值，记录并跳过
                if (g.getHitCount() >= 10) {
                    log.warn("[Ralph] 陷阱 {} 已触发 {} 次，暂停该模式", g.getPattern(), g.getHitCount());
                    DeliveryResult r = DeliveryResult.blocked("known_pitfall: " + g.getPattern());
                    r.setDiagnosed(true);
                    onDeliveryResult(jobKey, r, strategyName);
                    return r;
                }

                // 强制切换到建议策略
                DeliveryStrategy recommended = findStrategy(lastDiagnosis.getRecommendedStrategy());
                if (recommended != null && !recommended.name().equals(strategyName)) {
                    log.info("[Ralph] 强制切换策略: {} -> {}", strategyName, recommended.name());
                    lastDiagnosis = RalphFailureDiagnosis.builder()
                            .pattern(g.getPattern())
                            .description("guardrail hit: " + g.getTriggeredBy())
                .recommendedStrategy(normalizeStrategyName(g.getAction()))
                        .autoFixable(true)
                            .knownPitfall(true)
                            .matchedGuardrailId(g.getId())
                            .build();
                    continue;
                }
            }

            // 6. 尝试自动修复（如果可修复且不是已知坑）
            if (lastDiagnosis.isAutoFixable() && !lastDiagnosis.isKnownPitfall()) {
                log.info("[Ralph] 诊断: {} -> {}", lastDiagnosis.getPattern(), lastDiagnosis.getRecommendedStrategy());

                // 短暂等待后重试（网络/加载类问题）
                if ("element_timeout".equals(lastDiagnosis.getPattern()) || "network_error".equals(lastDiagnosis.getPattern())) {
                    safeSleep(BASE_SLEEP_MS);
                }

                // 验证码需要更长等待
                if ("captcha_detected".equals(lastDiagnosis.getPattern())) {
                    safeSleep(CAPTCHA_SLEEP_MS);
                }
                continue;
            }

            // 7. 无法修复，学习并返回失败
            if (!lastDiagnosis.isKnownPitfall()) {
                RalphGuardrail learned = guardrailsManager.learn(lastDiagnosis);
                log.info("[Ralph] 学习到新约束: {}", learned.getPattern());
            }

            result.setDiagnosed(true);
            session.setLastError(lastDiagnosis.getDescription());
            taskSessionRepository.save(session);
            onDeliveryResult(jobKey, result, strategyName);
            return result;
        }

        // 达到最大重试次数
        DeliveryResult finalResult = DeliveryResult.failed("max_attempts_reached",
                "达到最大重试次数(" + DEFAULT_MAX_ATTEMPTS + "): " + (lastDiagnosis != null ? lastDiagnosis.getPattern() : "unknown"));
        finalResult.setDiagnosed(true);
        onDeliveryResult(jobKey, finalResult, session.getCurrentStrategy());
        return finalResult;
    }

    /**
     * 诊断失败原因
     */
    public RalphFailureDiagnosis diagnose(DeliveryResult result, int attempt) {
        String errorType = result.getErrorType() != null ? result.getErrorType() : "";
        String message = result.getMessage() != null ? result.getMessage() : "";

        RalphFailureDiagnosis diagnosis = RalphFailureDiagnosis.fromErrorType(errorType, message);

        // 多次尝试同一策略失败，提高置信度
        if (attempt >= 2) {
            diagnosis.setAutoFixable(false); // 多次失败说明非临时性问题
        }

        return diagnosis;
    }

    /**
     * 结束会话
     */
    public void endSession(TaskSession session, String status) {
        session.setStatus(status);
        session.setFinishedAt(LocalDateTime.now());
        taskSessionRepository.save(session);
        log.info("[Ralph] 会话 {} 结束: {}", session.getSessionId(), status);
    }

    /**
     * 更新会话统计数据
     */
    public void updateSessionStats(TaskSession session, DeliveryResult result) {
        switch (result.getStatus()) {
            case SUCCESS -> session.setDelivered(session.getDelivered() + 1);
            case SKIPPED, ALREADY_DELIVERED -> session.setSkipped(session.getSkipped() + 1);
            case FAILED, BLOCKED_BY_GUARDRAIL -> session.setFailed(session.getFailed() + 1);
        }
        taskSessionRepository.save(session);
    }

    // ---- 内部辅助方法 ----

    private DeliveryStrategy getDefaultStrategy() {
        return strategies.stream()
                .min(Comparator.comparingInt(DeliveryStrategy::priority))
                .orElseThrow(() -> new IllegalStateException("No strategies available"));
    }

    private DeliveryStrategy selectStrategy(RalphFailureDiagnosis diagnosis, int attempt) {
        // 优先采纳 diagnosis 建议的策略（来自 guardrails 或 auto-fix）
        if (diagnosis != null && diagnosis.getRecommendedStrategy() != null
                && !diagnosis.getRecommendedStrategy().isBlank()) {
            DeliveryStrategy recommended = findStrategy(diagnosis.getRecommendedStrategy());
            if (recommended != null) {
                return recommended;
            }
        }
        // fallback：按 attempt 序号轮转策略链（不在同一策略上反复重试）
        int idx = (attempt - 1) % strategies.size();
        return strategies.get(idx);
    }

    private DeliveryStrategy findStrategy(String name) {
        if (name == null) return null;
        String normalized = normalizeStrategyName(name);
        return strategies.stream()
                .filter(s -> s.name().equalsIgnoreCase(normalized))
                .findFirst()
                .orElse(null);
    }

    /** 将各种 action 格式统一为策略名 */
    private String normalizeStrategyName(String name) {
        if (name == null) return "";
        String s = name.toLowerCase().trim();
        if (s.startsWith("switch_to_")) s = s.substring("switch_to_".length());
        if (s.startsWith("use_")) s = s.substring("use_".length());
        if (s.startsWith("wait_and_") || s.startsWith("refresh_and_")) s = "detail_page";
        return s;
    }

    /**
     * 安全 sleep：正确处理 interrupt
     * @param ms 睡眠毫秒数
     */
    private void safeSleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            log.debug("[Ralph] Sleep interrupted");
        }
    }

    private void onDeliveryResult(String jobKey, DeliveryResult result, String strategy) {
        if (callback != null) {
            callback.onResult(jobKey, result, strategy);
        }
    }
}
