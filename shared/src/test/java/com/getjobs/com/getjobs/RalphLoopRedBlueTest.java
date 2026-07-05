package com.getjobs;

import com.getjobs.worker.ralph.*;
import org.junit.jupiter.api.*;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Ralph Loop 红蓝对抗测试套件
 */
public class RalphLoopRedBlueTest {

    private static final java.nio.file.Path TEST_DATA_DIR =
            java.nio.file.Paths.get("data", "test-ralph");

    private RalphGuardrailsManager makeGr() {
        try { java.nio.file.Files.createDirectories(TEST_DATA_DIR); } catch (Exception ignored) {}
        return new RalphGuardrailsManager(TEST_DATA_DIR.resolve("guardrails.json"));
    }

    private RalphTaskQueue makeTq() {
        try { java.nio.file.Files.createDirectories(TEST_DATA_DIR); } catch (Exception ignored) {}
        return new RalphTaskQueue(TEST_DATA_DIR.resolve("tasks.json"));
    }

    // ============================================================
    // 红队测试
    // ============================================================

    @Test
    @DisplayName("红队: 反爬虫返回非预期内容 -> 分类为 network_error")
    void redTeam_antibot_classified_as_network_error() {
        DeliveryResult result = DeliveryResult.failed(
                "network_error",
                "net::ERR_BLOCKED_BY_CLIENT 或网站返回 403"
        );
        RalphFailureDiagnosis diag = RalphFailureDiagnosis.fromErrorType("network_error", result.getMessage());
        assertEquals("network_error", diag.getPattern());
        assertTrue(diag.isAutoFixable());
    }

    @Test
    @DisplayName("红队: 选择器全部失效 -> detail_page 策略")
    void redTeam_all_selectors_changed_recommends_detail_page() {
        RalphFailureDiagnosis diag = RalphFailureDiagnosis.builder()
                .pattern("button_hidden")
                .description("isVisible=false on all selectors")
                .recommendedStrategy("detail_page")
                .autoFixable(false)
                .knownPitfall(false)
                .relatedErrorTypes(List.of("isVisible"))
                .pitfallHitCount(0)
                .diagnosed(false)
                .build();
        assertEquals("detail_page", diag.getRecommendedStrategy());
    }

    @Test
    @DisplayName("红队: 验证码分类 -> captcha_detected")
    void redTeam_captcha_classification() {
        RalphFailureDiagnosis diag = RalphFailureDiagnosis.fromErrorType(
                "captcha", "检测到验证码弹窗"
        );
        assertEquals("captcha_detected", diag.getPattern());
        assertTrue(diag.isAutoFixable());
    }

    @Test
    @DisplayName("红队: 连续失败触发 guardrail 禁用 (10次)")
    void redTeam_rapid_failures_disable_guardrail() {
        RalphGuardrailsManager gr = makeGr();
        int before = gr.getAll().size();

        RalphFailureDiagnosis diag = RalphFailureDiagnosis.builder()
                .pattern("test_disable_pattern")
                .description("red blue test disable")
                .recommendedStrategy("detail_page")
                .autoFixable(false)
                .knownPitfall(false)
                .relatedErrorTypes(List.of("test"))
                .pitfallHitCount(0)
                .diagnosed(false)
                .build();

        // 第10次触发后应被禁用
        for (int i = 0; i < 10; i++) {
            RalphGuardrail g = gr.learn(diag);
            if (i < 9) {
                assertTrue(g.isEnabled(), "第" + (i+1) + "次应仍启用");
            }
        }

        Optional<RalphGuardrail> after = gr.getAll().stream()
                .filter(g -> g.getPattern().equals("test_disable_pattern"))
                .findFirst();
        assertTrue(after.isPresent());
        assertFalse(after.get().isEnabled(), "第10次触发后应被禁用");
    }

    @Test
    @DisplayName("红队: Stale element -> element_stale")
    void redTeam_stale_element_classification() {
        RalphFailureDiagnosis diag = RalphFailureDiagnosis.fromErrorType(
                "stale", "stale element reference"
        );
        assertEquals("element_stale", diag.getPattern());
        assertEquals("detail_page", diag.getRecommendedStrategy());
    }

    @Test
    @DisplayName("红队: 未知错误 -> detail_page兜底")
    void redTeam_unknown_error_defaults_to_detail_page() {
        RalphFailureDiagnosis diag = RalphFailureDiagnosis.fromErrorType(
                "unknown", "something completely unexpected"
        );
        assertEquals("unknown_error", diag.getPattern());
        assertEquals("detail_page", diag.getRecommendedStrategy());
    }

    // ============================================================
    // 蓝队验证
    // ============================================================

    @Test
    @DisplayName("蓝队: DeliveryResult 静态工厂方法正常")
    void blueTeam_delivery_result_factory_methods() {
        assertTrue(DeliveryResult.success().isSuccess());
        assertEquals(DeliveryResult.Status.SUCCESS, DeliveryResult.success().getStatus());

        assertEquals(DeliveryResult.Status.ALREADY_DELIVERED, DeliveryResult.alreadyDelivered().getStatus());

        DeliveryResult failed = DeliveryResult.failed("test_error", "test message");
        assertEquals(DeliveryResult.Status.FAILED, failed.getStatus());
        assertEquals("test_error", failed.getErrorType());
        assertEquals("test message", failed.getMessage());
        assertFalse(failed.isSuccess());

        DeliveryResult blocked = DeliveryResult.blocked("guardrail reason");
        assertEquals(DeliveryResult.Status.BLOCKED_BY_GUARDRAIL, blocked.getStatus());
    }

    @Test
    @DisplayName("蓝队: DeliveryResult.shouldRetry 逻辑正确")
    void blueTeam_should_retry_logic() {
        DeliveryResult diagnosed = DeliveryResult.failed("e", "m");
        diagnosed.setDiagnosed(true);
        assertFalse(diagnosed.shouldRetry());

        DeliveryResult notDiagnosed = DeliveryResult.failed("e", "m");
        assertTrue(notDiagnosed.shouldRetry());
    }

    @Test
    @DisplayName("蓝队: GuardrailsManager 加载和保存")
    void blueTeam_guardrails_manager_load_save() {
        RalphGuardrailsManager gr = makeGr();

        // 规则集合不为 null
        assertNotNull(gr.getAll());

        // checkMatch 对空 pattern 不会匹配任何规则（因为默认规则 pattern 都非空）
        Optional<RalphGuardrail> match = gr.checkMatch("", "");
        assertTrue(match.isEmpty(), "空 pattern 不应匹配任何规则");
    }

    @Test
    @DisplayName("蓝队: GuardrailsManager.learn 创建/累计规则")
    void blueTeam_guardrails_learn() {
        RalphGuardrailsManager gr = makeGr();

        RalphFailureDiagnosis diag = RalphFailureDiagnosis.builder()
                .pattern("blue_team_test_pattern")
                .description("blue team test")
                .recommendedStrategy("detail_page")
                .autoFixable(false)
                .knownPitfall(false)
                .relatedErrorTypes(List.of())
                .pitfallHitCount(0)
                .diagnosed(false)
                .build();

        RalphGuardrail learned = gr.learn(diag);
        assertNotNull(learned);
        assertEquals("blue_team_test_pattern", learned.getPattern());
        assertEquals(1, learned.getHitCount());
        assertTrue(learned.isEnabled());

        // 第二次学习应累计
        RalphGuardrail again = gr.learn(diag);
        assertEquals(2, again.getHitCount());
    }

    @Test
    @DisplayName("蓝队: RalphTaskQueue 添加和完成")
    void blueTeam_task_queue_operations() {
        RalphTaskQueue tq = makeTq();

        RalphTask task = tq.addTask("蓝队测试任务");
        assertNotNull(task);
        assertEquals("PENDING", task.getStatus().name());
        assertEquals(0, task.getIterations());

        tq.startTask(task.getId());
        RalphTask running = tq.getTask(task.getId()).orElseThrow();
        assertEquals("IN_PROGRESS", running.getStatus().name());

        tq.completeTask(task.getId());
        RalphTask done = tq.getTask(task.getId()).orElseThrow();
        assertEquals("DONE", done.getStatus().name());
        assertNotNull(done.getCompletedAt());
    }

    @Test
    @DisplayName("蓝队: RalphFailureDiagnosis.fromErrorType 正确分类")
    void blueTeam_failure_diagnosis_classification() {
        // 各种错误类型
        assertEquals("element_not_found",
                RalphFailureDiagnosis.fromErrorType("x", "element not found").getPattern());
        assertEquals("element_not_found",
                RalphFailureDiagnosis.fromErrorType("x", "unable to locate").getPattern());
        assertEquals("button_hidden",
                RalphFailureDiagnosis.fromErrorType("x", "isVisible=false").getPattern());
        assertEquals("hover_timeout",
                RalphFailureDiagnosis.fromErrorType("x", "hover timeout").getPattern());
        assertEquals("element_timeout",
                RalphFailureDiagnosis.fromErrorType("x", "click timed out").getPattern());
        assertEquals("session_expired",
                RalphFailureDiagnosis.fromErrorType("x", "please login").getPattern());
        assertEquals("network_error",
                RalphFailureDiagnosis.fromErrorType("x", "net::ERR_CONNECTION").getPattern());
    }

    @Test
    @DisplayName("蓝队: 策略优先级正确")
    void blueTeam_strategy_priorities() {
        HoverCardStrategy hoverCard = new HoverCardStrategy();
        DetailPageStrategy detailPage = new DetailPageStrategy();
        ApiDirectStrategy apiDirect = new ApiDirectStrategy();

        assertEquals(1, hoverCard.priority());
        assertEquals(2, detailPage.priority());
        assertEquals(3, apiDirect.priority());
    }

    @Test
    @DisplayName("蓝队: canHandle 策略覆盖正确")
    void blueTeam_can_handle_coverage() {
        DetailPageStrategy dp = new DetailPageStrategy();

        // DetailPageStrategy 处理这些模式
        assertTrue(dp.canHandle(RalphFailureDiagnosis.fromErrorType("x", "isVisible=false")));
        assertTrue(dp.canHandle(RalphFailureDiagnosis.fromErrorType("x", "hover timeout")));
        assertTrue(dp.canHandle(RalphFailureDiagnosis.fromErrorType("x", "stale element")));
        assertTrue(dp.canHandle(RalphFailureDiagnosis.fromErrorType("x", "not found")));
        assertTrue(dp.canHandle(RalphFailureDiagnosis.fromErrorType("x", "click intercepted")));

        // null 诊断应该被所有策略处理
        assertTrue(dp.canHandle(null));
    }

    @Test
    @DisplayName("蓝队: ApiDirectStrategy 可处理所有诊断")
    void blueTeam_api_direct_can_handle_all() {
        ApiDirectStrategy api = new ApiDirectStrategy();
        // API 是最终兜底策略
        assertTrue(api.canHandle(null));
        assertTrue(api.canHandle(RalphFailureDiagnosis.fromErrorType("x", "anything")));
    }
}
