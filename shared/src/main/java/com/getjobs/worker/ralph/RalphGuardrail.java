package com.getjobs.worker.ralph;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;

/**
 * Ralph Guardrail 陷阱规则
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class RalphGuardrail {

    private String id;
    private String pattern;
    private String triggeredBy;
    private String action;          // "skip", "switch_to_detail_page", "switch_to_api"
    private int hitCount;
    private LocalDateTime createdAt;
    private LocalDateTime lastHitAt;
    private boolean enabled;

    public void incrementHit() {
        this.hitCount++;
        this.lastHitAt = LocalDateTime.now();
    }
}
