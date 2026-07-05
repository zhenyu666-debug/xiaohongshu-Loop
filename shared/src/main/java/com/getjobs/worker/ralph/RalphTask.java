package com.getjobs.worker.ralph;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;

/**
 * Ralph 任务队列中的单个任务
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class RalphTask {

    public enum Status {
        PENDING, IN_PROGRESS, DONE, FAILED, SKIPPED
    }

    private String id;
    private String description;
    private Status status;
    private int iterations;
    private int maxIterations;
    private LocalDateTime createdAt;
    private LocalDateTime completedAt;
    private String lastError;
    private String assignedStrategy;
}
