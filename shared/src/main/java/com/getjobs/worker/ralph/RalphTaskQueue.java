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
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * Ralph 任务队列管理器
 * 负责跨会话追踪任务进度，类似 prd.json
 */
@Slf4j
@Component
public class RalphTaskQueue {

    private final Path tasksFile;
    private static final int MAX_ITERATIONS_DEFAULT = 5;
    private static final long FLUSH_INTERVAL_MS = 2000L;

    private final ConcurrentHashMap<String, RalphTask> tasks = new ConcurrentHashMap<>();
    private final ObjectMapper objectMapper;
    private final ScheduledExecutorService scheduler;
    private volatile boolean dirty = false;

    public RalphTaskQueue() {
        this(Paths.get("data", "ralph-tasks.json"));
    }

    /** 支持注入路径的构造函数（用于测试隔离） */
    public RalphTaskQueue(Path tasksFile) {
        this.tasksFile = tasksFile;
        this.objectMapper = new ObjectMapper()
                .registerModule(new JavaTimeModule())
                .enable(SerializationFeature.INDENT_OUTPUT);
        this.scheduler = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "RalphTaskQueue-flush");
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
        // Final flush on shutdown
        if (dirty) save();
    }

    public void load() {
        if (!Files.exists(tasksFile)) {
            save();
            return;
        }
        try {
            TaskQueueData data = objectMapper.readValue(tasksFile.toFile(), TaskQueueData.class);
            tasks.clear();
            for (RalphTask t : data.getTasks()) {
                tasks.put(t.getId(), t);
            }
            log.info("加载了 {} 个 Ralph 任务", tasks.size());
        } catch (IOException e) {
            log.warn("加载 ralph-tasks.json 失败: {}", e.getMessage());
        }
    }

    public void save() {
        try {
            Files.createDirectories(tasksFile.getParent());
            TaskQueueData data = new TaskQueueData();
            data.setTasks(new ArrayList<>(tasks.values()));
            objectMapper.writeValue(tasksFile.toFile(), data);
        } catch (IOException e) {
            log.error("保存 ralph-tasks.json 失败: {}", e.getMessage());
        }
    }

    private void markDirty() { dirty = true; }

    public RalphTask addTask(String description) {
        RalphTask task = RalphTask.builder()
                .id("t_" + UUID.randomUUID().toString().substring(0, 8))
                .description(description)
                .status(RalphTask.Status.PENDING)
                .iterations(0)
                .maxIterations(MAX_ITERATIONS_DEFAULT)
                .createdAt(LocalDateTime.now())
                .build();
        tasks.put(task.getId(), task);
        markDirty();
        return task;
    }

    public void startTask(String id) {
        RalphTask t = tasks.get(id);
        if (t != null) {
            t.setStatus(RalphTask.Status.IN_PROGRESS);
            t.setAssignedStrategy(t.getAssignedStrategy());
            markDirty();
        }
    }

    public void completeTask(String id) {
        RalphTask t = tasks.get(id);
        if (t != null) {
            t.setStatus(RalphTask.Status.DONE);
            t.setCompletedAt(LocalDateTime.now());
            markDirty();
        }
    }

    public void failTask(String id, String error) {
        RalphTask t = tasks.get(id);
        if (t != null) {
            t.setIterations(t.getIterations() + 1);
            if (t.getIterations() >= t.getMaxIterations()) {
                t.setStatus(RalphTask.Status.FAILED);
            }
            t.setLastError(error);
            markDirty();
        }
    }

    public void skipTask(String id) {
        RalphTask t = tasks.get(id);
        if (t != null) {
            t.setStatus(RalphTask.Status.SKIPPED);
            t.setCompletedAt(LocalDateTime.now());
            markDirty();
        }
    }

    public void recordIteration(String id, String strategy) {
        RalphTask t = tasks.get(id);
        if (t != null) {
            t.setIterations(t.getIterations() + 1);
            t.setAssignedStrategy(strategy);
            markDirty();
        }
    }

    public Optional<RalphTask> getNextPending() {
        return tasks.values().stream()
                .filter(t -> t.getStatus() == RalphTask.Status.PENDING)
                .findFirst();
    }

    public Optional<RalphTask> getTask(String id) {
        return Optional.ofNullable(tasks.get(id));
    }

    public List<RalphTask> getAll() {
        return new ArrayList<>(tasks.values());
    }

    public List<RalphTask> getPending() {
        return tasks.values().stream()
                .filter(t -> t.getStatus() == RalphTask.Status.PENDING)
                .toList();
    }

    public List<RalphTask> getInProgress() {
        return tasks.values().stream()
                .filter(t -> t.getStatus() == RalphTask.Status.IN_PROGRESS)
                .toList();
    }

    // JSON 结构
    @lombok.Data
    private static class TaskQueueData {
        private List<RalphTask> tasks = new ArrayList<>();
    }
}
