package com.getjobs.worker.ralph;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.List;

/**
 * Ralph Loop 失败诊断结果
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class RalphFailureDiagnosis {

    private String pattern;
    private String description;
    private String recommendedStrategy;
    private boolean knownPitfall;
    private String matchedGuardrailId;
    private boolean autoFixable;
    private List<String> relatedErrorTypes;
    private int pitfallHitCount;
    private boolean diagnosed;

    public static RalphFailureDiagnosis fromErrorType(String errorType, String message) {
        String pattern = classifyErrorPattern(errorType, message);
        return RalphFailureDiagnosis.builder()
                .pattern(pattern)
                .description(message)
                .recommendedStrategy(recommendStrategy(pattern))
                .knownPitfall(false)
                .autoFixable(true)
                .relatedErrorTypes(List.of(errorType))
                .pitfallHitCount(1)
                .build();
    }

    private static String classifyErrorPattern(String errorType, String message) {
        String m = message.toLowerCase();
        if (m.contains("visible") || m.contains("hidden") || m.contains("not visible")) {
            return "button_hidden";
        }
        if (m.contains("companydetail") || m.contains("非预期页面") || m.contains("EdgeOne") || m.contains("redirect")) {
            return "companydetail_redirect";
        }
        if (m.contains("timeout") || m.contains("timed out")) {
            if (m.contains("hover") || m.contains("mouse")) {
                return "hover_timeout";
            }
            return "element_timeout";
        }
        if (m.contains("stale") || m.contains(" detached")) {
            return "element_stale";
        }
        if (m.contains("captcha") || m.contains("验证") || m.contains("验证码")) {
            return "captcha_detected";
        }
        if (m.contains("network") || m.contains("net::") || m.contains("connection")) {
            return "network_error";
        }
        if (m.contains("not found") || m.contains("unable to locate") || m.contains("找不到")) {
            return "element_not_found";
        }
        if (m.contains("click") && m.contains("intercept")) {
            return "click_intercepted";
        }
        if (m.contains("login") || m.contains("登录")) {
            return "session_expired";
        }
        return "unknown_error";
    }

    private static String recommendStrategy(String pattern) {
        return switch (pattern) {
            case "companydetail_redirect" -> "api_direct";
            case "button_hidden" -> "detail_page";
            case "hover_timeout" -> "detail_page";
            case "element_stale" -> "detail_page";
            case "element_not_found" -> "detail_page";
            case "click_intercepted" -> "detail_page";
            case "captcha_detected" -> "wait_and_retry";
            case "network_error" -> "wait_and_retry";
            case "session_expired" -> "relogin";
            default -> "detail_page";
        };
    }
}
