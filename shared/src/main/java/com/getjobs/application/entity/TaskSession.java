package com.getjobs.application.entity;

import jakarta.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "task_session")
public class TaskSession {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "session_id", unique = true)
    private String sessionId;

    @Column(name = "platform")
    private String platform; // "zhilian", "liepin"

    @Column(name = "keyword")
    private String keyword;

    @Column(name = "total_jobs")
    private Integer totalJobs;

    @Column(name = "delivered")
    private Integer delivered = 0;

    @Column(name = "skipped")
    private Integer skipped = 0;

    @Column(name = "failed")
    private Integer failed = 0;

    @Column(name = "current_strategy")
    private String currentStrategy;

    @Column(name = "status")
    private String status; // RUNNING, COMPLETED, PAUSED, FAILED

    @Column(name = "last_error")
    private String lastError;

    @Column(name = "started_at")
    private LocalDateTime startedAt;

    @Column(name = "finished_at")
    private LocalDateTime finishedAt;

    @Column(name = "guardrails_triggered")
    private Integer guardrailsTriggered = 0;

    @Column(name = "strategy_switches")
    private Integer strategySwitches = 0;

    public enum Status {
        RUNNING, COMPLETED, PAUSED, FAILED
    }
}
