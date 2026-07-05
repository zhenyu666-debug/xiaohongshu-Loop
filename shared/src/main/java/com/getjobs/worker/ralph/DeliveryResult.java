package com.getjobs.worker.ralph;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;

/**
 * 投递操作的结果封装
 */
@Data
@Builder
@AllArgsConstructor
public class DeliveryResult {

    public enum Status {
        SUCCESS,         // 投递成功
        ALREADY_DELIVERED, // 已投递过
        FAILED,           // 失败
        BLOCKED_BY_GUARDRAIL, // 被 guardrail 拦截
        SKIPPED           // 跳过（无法投递）
    }

    private Status status;
    private String message;
    private String errorType;    // "timeout", "element_not_found", "not_visible", "captcha", "network_error"
    private String stackTrace;
    private boolean diagnosed;   // 是否已诊断过
    private String strategyName; // 执行成功的策略名

    public boolean isSuccess() {
        return status == Status.SUCCESS;
    }

    public boolean shouldRetry() {
        return status == Status.FAILED && !diagnosed;
    }

    public static DeliveryResult success() {
        return DeliveryResult.builder().status(Status.SUCCESS).message("投递成功").build();
    }

    public static DeliveryResult success(String strategyName) {
        return DeliveryResult.builder().status(Status.SUCCESS)
                .message(strategyName).build();
    }

    public static DeliveryResult alreadyDelivered() {
        return DeliveryResult.builder().status(Status.ALREADY_DELIVERED).message("已投递").build();
    }

    public static DeliveryResult failed(String errorType, String message) {
        return DeliveryResult.builder().status(Status.FAILED)
                .errorType(errorType).message(message).build();
    }

    public static DeliveryResult blocked(String reason) {
        return DeliveryResult.builder().status(Status.BLOCKED_BY_GUARDRAIL).message(reason).build();
    }

    public static DeliveryResult skipped(String reason) {
        return DeliveryResult.builder().status(Status.SKIPPED).message(reason).build();
    }
}
