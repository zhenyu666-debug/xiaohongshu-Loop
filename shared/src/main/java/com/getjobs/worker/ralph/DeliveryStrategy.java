package com.getjobs.worker.ralph;

import com.microsoft.playwright.Locator;
import com.microsoft.playwright.Page;

/**
 * 投递策略接口
 * Ralph Loop 通过策略链实现自动降级
 */
public interface DeliveryStrategy {

    /**
     * 策略名称
     */
    String name();

    /**
     * 该策略的优先级（数字越小优先级越高）
     */
    int priority();

    /**
     * 是否可以处理当前诊断结果
     */
    boolean canHandle(RalphFailureDiagnosis diagnosis);

    /**
     * 执行投递
     * @param page Playwright Page
     * @param jobKey 岗位唯一标识（公司名_岗位名）
     * @param jobLink 岗位链接（可选，用于详情页策略）
     * @return 投递结果
     */
    DeliveryResult deliver(Page page, String jobKey, String jobLink);

    /**
     * 检查该岗位是否已投递（所有策略共用）
     * 仅检查指定卡片容器内的按钮，避免全局弹窗误判
     */
    default boolean isAlreadyDelivered(Locator card) {
        try {
            Object result = card.evaluate(
                    "el => { " +
                    "  const btns = el.querySelectorAll('button'); " +
                    "  for (const b of btns) { " +
                    "    const t = b.textContent || ''; " +
                    "    if (t.includes('已投递') || t.includes('已申请') || t.includes('投递成功')) return t; " +
                    "  } " +
                    "  return null; " +
                    "}"
            );
            return result != null;
        } catch (Exception ignored) {}
        return false;
    }

    /**
     * 兼容旧调用：检查整个页面是否显示投递成功弹窗
     */
    default boolean isPageShowingDeliverySuccess(Page page) {
        try {
            // 检查 button
            Object result = page.evaluate(
                    "() => { " +
                    "  const btns = document.querySelectorAll('button'); " +
                    "  for (const b of btns) { " +
                    "    const t = b.textContent || ''; " +
                    "    if (t.includes('已投递') || t.includes('已申请') || t.includes('投递成功')) return t; " +
                    "  } " +
                    "  return null; " +
                    "}"
            );
            if (result != null) return true;

            // 检查 div/p/span 中的成功文案（智联详情页样式 + 猎聘"已沟通"状态）
            result = page.evaluate(
                    "() => { " +
                    "  const els = document.querySelectorAll('div, p, span, h1, h2, h3'); " +
                    "  for (const el of els) { " +
                    "    const t = (el.textContent || '').trim(); " +
                    "    if (t.length > 80) continue; " +
                    "    if (t.includes('简历已成功投递') || t.includes('投递成功') || t.includes('已为您投递') || t.includes('您的简历已成功')) return t.substring(0, 80); " +
                    "    if (t.includes('已与该用户沟通过') || t.includes('沟通中') || t === '继续聊' || t === '已沟通') return t; " +
                    "  } " +
                    "  return null; " +
                    "}"
            );
            return result != null;
        } catch (Exception ignored) {}
        return false;
    }

    /**
     * 检查是否停留在搜索结果列表页（投递后应返回列表）
     * 支持智联、猎聘等平台
     */
    default boolean isOnSearchListPage(Page page) {
        try {
            String url = page.url();
            // 智联招聘 — 详情页路径含 /job/ 后跟数字 ID；列表页是 /sou/ 或 /search
            if (url.contains("zhaopin.com/sou/") || url.contains("zhaopin.com/search")) {
                return true;
            }
            if (url.contains("zhaopin.com/job/")) {
                return false; // 详情页
            }
            // 猎聘：zhaopin 子域列表页是 /zhaopin/...query；详情页是 /job/xxx.shtml
            if (url.contains("liepin.com/zhaopin/")) {
                return true;
            }
            if (url.contains("liepin.com/job/")) {
                return false; // 详情页
            }
            return false;
        } catch (Exception ignored) {}
        return false;
    }

    /**
     * 带 card locator 的投递（策略直接操作已知卡片，不重新搜索）
     */
    default DeliveryResult deliverWithCard(Page page, Locator card, String jobKey) {
        return deliver(page, jobKey, null);
    }

    /**
     * 关闭投递后弹出的标签页
     */
    default void closePopupTabs(Page page) {
        try {
            int before = page.context().pages().size();
            for (int i = before - 1; i > 0; i--) {
                try {
                    page.context().pages().get(i).close();
                } catch (Exception ignored) {}
            }
        } catch (Exception ignored) {}
    }

    /**
     * 检测是否被重定向到非预期页面（如 companydetail/腾讯防水墙/安全验证页）
     */
    default boolean isRedirectedToUnexpectedPage(Page page) {
        try {
            String url = page.url();
            return url.contains("companydetail")
                || url.contains("tencent-cloud")
                || url.contains("EdgeOne")
                || url.contains("/security/")
                || url.contains("captcha")
                || url.contains("verify");
        } catch (Exception ignored) {}
        return false;
    }
}
