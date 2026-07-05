package com.getjobs.worker.ralph;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * Ralph Guardrails 持久化管理器
 * 负责加载、保存和学习陷阱约束
 */
@Slf4j
@Component
public class RalphGuardrailsManager {

    private final Path guardrailsFile;
    private static final int AUTO_DISABLE_THRESHOLD = 10;
    private static final long FLUSH_INTERVAL_MS = 2000L;

    private final ConcurrentHashMap<String, RalphGuardrail> guardrails = new ConcurrentHashMap<>();
    private final ObjectMapper objectMapper;
    private final ScheduledExecutorService scheduler;
    private volatile boolean dirty = false;

    public RalphGuardrailsManager() {
        this(Paths.get("data", "ralph-guardrails.json"));
    }

    /** 支持注入路径的构造函数（用于测试隔离） */
    public RalphGuardrailsManager(Path guardrailsFile) {
        this.guardrailsFile = guardrailsFile;
        this.objectMapper = new ObjectMapper()
                .registerModule(new JavaTimeModule())
                .enable(SerializationFeature.INDENT_OUTPUT);
        this.scheduler = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "RalphGuardrails-flush");
            t.setDaemon(true);
            return t;
        });
    }

    @PostConstruct
    public void init() {
        load();
        scheduler.scheduleAtFixedRate(() -> {
            if (dirty) {
                save();
                dirty = false;
            }
        }, FLUSH_INTERVAL_MS, FLUSH_INTERVAL_MS, TimeUnit.MILLISECONDS);
    }

    @PreDestroy
    public void shutdown() {
        scheduler.shutdown();
        try {
            if (!scheduler.awaitTermination(5, TimeUnit.SECONDS)) {
                scheduler.shutdownNow();
            }
        } catch (InterruptedException e) {
            scheduler.shutdownNow();
            Thread.currentThread().interrupt();
        }
        if (dirty) save();
    }

    public void load() {
        if (!Files.exists(guardrailsFile)) {
            log.info("Guardrails 文件不存在，创建默认规则");
            createDefaultGuardrails();
            save();
            return;
        }
        try {
            GuardrailsData data = objectMapper.readValue(guardrailsFile.toFile(), GuardrailsData.class);
            guardrails.clear();
            for (RalphGuardrail g : data.getPitfalls()) {
                guardrails.put(g.getId(), g);
            }
            log.info("加载了 {} 条 guardrails 规则", guardrails.size());
        } catch (IOException e) {
            log.warn("加载 guardrails 失败: {}, 创建默认规则", e.getMessage());
            createDefaultGuardrails();
        }
    }

    public void save() {
        try {
            Files.createDirectories(guardrailsFile.getParent());
            GuardrailsData data = new GuardrailsData();
            data.setPitfalls(new ArrayList<>(guardrails.values()));
            objectMapper.writeValue(guardrailsFile.toFile(), data);
            log.debug("Guardrails 已保存到 {}", guardrailsFile);
        } catch (IOException e) {
            log.error("保存 guardrails 失败: {}", e.getMessage());
        }
    }

    /**
     * 检查给定错误类型是否匹配已知陷阱
     */
    public Optional<RalphGuardrail> checkMatch(String pattern, String message) {
        return guardrails.values().stream()
                .filter(g -> g.isEnabled() && matchesPattern(pattern, message, g))
                .findFirst();
    }

    private boolean matchesPattern(String pattern, String message, RalphGuardrail g) {
        if (g.getPattern().equals(pattern)) return true;
        String m = (message != null ? message : "").toLowerCase();
        String t = (g.getTriggeredBy() != null ? g.getTriggeredBy() : "").toLowerCase();
        return m.contains(t) || t.contains(m);
    }

    private void markDirty() { dirty = true; }

    /**
     * 记录一个失败的诊断结果，学习新约束
     */
    public RalphGuardrail learn(RalphFailureDiagnosis diagnosis) {
        String id = "gr_" + diagnosis.getPattern() + "_" + System.currentTimeMillis() % 10000;
        RalphGuardrail g = RalphGuardrail.builder()
                .id(id)
                .pattern(diagnosis.getPattern())
                .triggeredBy(diagnosis.getDescription())
                .action(diagnosis.getRecommendedStrategy())
                .hitCount(1)
                .createdAt(java.time.LocalDateTime.now())
                .lastHitAt(java.time.LocalDateTime.now())
                .enabled(true)
                .build();

        // 检查是否已存在相似规则
        Optional<RalphGuardrail> existing = guardrails.values().stream()
                .filter(gr -> gr.getPattern().equals(diagnosis.getPattern()))
                .findFirst();

        if (existing.isPresent()) {
            RalphGuardrail e = existing.get();
            e.incrementHit();
            if (e.getHitCount() >= AUTO_DISABLE_THRESHOLD) {
                e.setEnabled(false);
                log.warn("Guardrail {} 触发次数过多({})，已自动禁用", e.getPattern(), e.getHitCount());
            }
            markDirty();
            return e;
        }

        guardrails.put(id, g);
        log.info("Ralph 学习到新约束: {} -> {}", diagnosis.getPattern(), diagnosis.getRecommendedStrategy());
        markDirty();
        return g;
    }

    /**
     * 移除指定 guardrail
     */
    public void remove(String id) {
        guardrails.remove(id);
        markDirty();
    }

    /**
     * 启用/禁用指定规则
     */
    public void setEnabled(String id, boolean enabled) {
        RalphGuardrail g = guardrails.get(id);
        if (g != null) {
            g.setEnabled(enabled);
            markDirty();
        }
    }

    public List<RalphGuardrail> getAll() {
        return new ArrayList<>(guardrails.values());
    }

    private void createDefaultGuardrails() {
        guardrails.clear();

        addDefault("gr_hover_timeout",
                "hover_timeout",
                "hover timeout after 600ms",
                "hover_card");
        addDefault("gr_button_hidden",
                "button_hidden",
                "isVisible=false on all selectors",
                "detail_page");
        addDefault("gr_captcha",
                "captcha_detected",
                "captcha verification required",
                "detail_page");
        addDefault("gr_stale",
                "element_stale",
                "stale element reference",
                "detail_page");
        addDefault("gr_session_expired",
                "session_expired",
                "login or session expired",
                "api_direct");
    }

    private void addDefault(String id, String pattern, String trigger, String action) {
        RalphGuardrail g = RalphGuardrail.builder()
                .id(id)
                .pattern(pattern)
                .triggeredBy(trigger)
                .action(action)
                .hitCount(0)
                .createdAt(java.time.LocalDateTime.now())
                .lastHitAt(java.time.LocalDateTime.now())
                .enabled(true)
                .build();
        guardrails.put(id, g);
    }

    // JSON 结构
    @lombok.Data
    private static class GuardrailsData {
        private List<RalphGuardrail> pitfalls = new ArrayList<>();
    }
}
