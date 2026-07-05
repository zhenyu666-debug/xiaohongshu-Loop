package com.getjobs.worker.ralph;

import com.microsoft.playwright.Page;
import com.microsoft.playwright.Locator;
import com.microsoft.playwright.options.WaitUntilState;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 策略2: 详情页投递
 * 点击岗位卡片进入详情页后投递
 */
@Slf4j
@Component
public class DetailPageStrategy implements DeliveryStrategy {

    private static final long NAV_WAIT_MS = 1000L;
    private static final long PAGE_LOAD_WAIT_MS = 500L;
    private static final long POST_CLICK_WAIT_MS = 800L;

    private static final String[] APPLY_BUTTON_SELECTORS = {
            // 智联新版 - 高优先级
            "button.collect-and-apply__btn",
            "button:has-text('立即投递')",
            "a:has-text('立即投递')",
            "button:has-text('投递')",
            "a:has-text('投递')",
            "span:has-text('立即投递')",
            "span:has-text('投递')",
            // 智联 - class 变体
            "button[class*='apply']",
            "a[class*='apply']",
            "[class*='deliver']",
            "[class*='collect-and-apply']",
            ".btn-apply",
            ".apply-btn",
            "button.btn-primary",
            "a.btn-primary",
            ".job-apply-button",
            "[class*='submit']",
            ".job-detail-btn button",
            ".resume-container button",
            ".apply-container button",
            "[data-action='apply']",
            "[data-type='apply']",
            "button[class*='action']",
            "a[class*='action']",
            "[class*='apply'] button",
            // 猎聘
            "button:has-text('聊一聊')",
            "a:has-text('聊一聊')",
            "button:has-text('立即沟通')",
            "a:has-text('立即沟通')",
            "[class*='liao'] button",
            "[class*='liao'] a",
            "[class*='chat'] button",
            "[class*='chat'] a"
    };

    @Override
    public String name() {
        return "detail_page";
    }

    @Override
    public int priority() {
        return 2;
    }

    @Override
    public boolean canHandle(RalphFailureDiagnosis diagnosis) {
        if (diagnosis == null) return true;
        String p = diagnosis.getPattern();
        return "button_hidden".equals(p)
                || "hover_timeout".equals(p)
                || "element_stale".equals(p)
                || "element_not_found".equals(p)
                || "click_intercepted".equals(p)
                || "companydetail_redirect".equals(p)
                || "detail_page".equals(diagnosis.getRecommendedStrategy());
    }

    @Override
    public DeliveryResult deliver(Page page, String jobKey, String jobLink) {
        try {
            String resolvedLink = resolveJobLink(page, jobKey, jobLink);
            if (resolvedLink == null) {
                navigateBackToListing(page);
                return DeliveryResult.failed("element_not_found", "无法获取岗位链接: " + jobKey);
            }

            // 导航到详情页
            Page popup = null;
            int pagesBefore = page.context().pages().size();

            try {
                page.navigate(resolvedLink, new Page.NavigateOptions()
                        .setWaitUntil(WaitUntilState.DOMCONTENTLOADED)
                        .setTimeout(30000));
            } catch (Exception e) {
                // 可能是在新标签页打开
                try {
                    page.locator("a[href*='" + extractJobId(resolvedLink) + "']").first().click();
                    safeSleep(NAV_WAIT_MS);
                } catch (Exception e2) {
                    navigateBackToListing(page);
                    return DeliveryResult.failed("navigation_error", "无法打开详情页: " + e.getMessage());
                }
            }

            // 等待详情页加载
            safeSleep(PAGE_LOAD_WAIT_MS);

            // 检查是否弹出新标签页
            if (page.context().pages().size() > pagesBefore) {
                popup = page.context().pages().get(page.context().pages().size() - 1);
                popup.waitForLoadState();
                safeSleep(PAGE_LOAD_WAIT_MS);
            }

            Page targetPage = popup != null ? popup : page;

            // 检查是否被重定向到非预期页面（如 companydetail）
            if (isRedirectedToUnexpectedPage(targetPage)) {
                if (popup != null) popup.close();
                navigateBackToListing(page);
                return DeliveryResult.failed("companydetail_redirect", "详情页被重定向到非预期页面");
            }

            // 检查详情页是否已投递（用全页弹窗检查）
            if (isPageShowingDeliverySuccess(targetPage)) {
                if (popup != null) popup.close();
                navigateBackToListing(page);
                return DeliveryResult.alreadyDelivered();
            }

            // 找投递按钮并点击
            DeliveryResult result = clickApplyOnPage(targetPage);
            if (popup != null) popup.close();
            navigateBackToListing(page);

            return result;

        } catch (Exception e) {
            return DeliveryResult.failed("detail_page_exception", e.getMessage());
        }
    }

    private DeliveryResult clickApplyOnPage(Page p) {
        // 智联工作流弹窗关闭
        try {
            p.evaluate("() => document.querySelectorAll('.a-modal.a-job-apply-workflow-close, .a-modal[role=\"dialog\"]').forEach(el => el.click())");
            safeSleep(300);
        } catch (Exception ignored) {}

        for (String sel : APPLY_BUTTON_SELECTORS) {
            try {
                Locator btn = p.locator(sel);
                if (btn.count() == 0) continue;

                // 尝试1: Playwright 等待 enabled 后点击
                if (waitUntilEnabled(p, btn)) {
                    btn.first().scrollIntoViewIfNeeded();
                    btn.first().click(new Locator.ClickOptions().setTimeout(3000));
                    safeSleep(POST_CLICK_WAIT_MS);
                    closePopupTabs(p);
                    if (isPageShowingDeliverySuccess(p)) return DeliveryResult.success(name());
                }

                // 尝试2: 按钮存在 → 直接 force 点击
                if (btn.count() > 0) {
                    btn.first().scrollIntoViewIfNeeded();
                    btn.first().click(new Locator.ClickOptions().setForce(true).setTimeout(3000));
                    safeSleep(POST_CLICK_WAIT_MS);
                    closePopupTabs(p);
                    if (isPageShowingDeliverySuccess(p)) return DeliveryResult.success(name());
                }
            } catch (Exception e) {
                log.debug("DetailPageStrategy selector '{}' failed: {}", sel, e.getMessage());
            }
        }
        return DeliveryResult.failed("apply_button_not_found", "详情页找不到投递按钮");
    }

    private boolean waitUntilEnabled(Page page, Locator btn) {
        long deadline = System.currentTimeMillis() + 2000L;
        while (System.currentTimeMillis() < deadline) {
            try {
                if (btn.first().isEnabled()) return true;
            } catch (Exception ignored) {}
            safeSleep(150);
        }
        return false;
    }

    private String resolveJobLink(Page page, String jobKey, String jobLink) {
        if (jobLink != null && !jobLink.isBlank()) {
            // lp: 前缀说明 jobLink = "lp:岗位名" 或 "lp:公司名-岗位名"
            // 无法从 lp: 前缀还原 URL，需要从当前页面卡片中找
            if (jobLink.startsWith("lp:")) {
                String keyword = jobLink.substring("lp:".length()).trim();
                return findLinkByKeyword(page, keyword);
            }
            return jobLink;
        }

        return null;
    }

    /**
     * 从页面卡片列表中找到匹配关键词的岗位链接
     */
    private String findLinkByKeyword(Page page, String keyword) {
        try {
            Locator cards = page.locator(
                    "ul.joblist-box__list > li, "
                    + ".joblist-box__item, "
                    + "div.joblist-box__list > div, "
                    + "ul.tab-content__joblist > li, "
                    + "[class*='job-item'], "
                    + ".job-box__item, "
                    + "div[class*='joblist'] > div"
            );
            int count = cards.count();
            for (int i = 0; i < count; i++) {
                Locator card = cards.nth(i);
                try {
                    Locator link = card.locator("a[href]");
                    if (link.count() == 0) continue;
                    String href = link.first().getAttribute("href");
                    if (href == null || href.contains("/company/")) continue;
                    // 匹配关键词（取标题文本做模糊匹配）
                    Locator titleEl = card.locator(
                            "div.jobinfo__name, [class*='jobinfo__name'], "
                            + "[class*='job-name'], a[class*='name'], span[class*='name']"
                    );
                    if (titleEl.count() > 0) {
                        String title = titleEl.first().textContent();
                        if (title != null && title.contains(keyword)) {
                            return href.startsWith("http") ? href : "https://www.liepin.com" + href;
                        }
                    }
                } catch (Exception ignored) {}
            }
        } catch (Exception ignored) {}
        return null;
    }

    /**
     * 从卡片中提取链接，然后走详情页投递流程
     */
    @Override
    public DeliveryResult deliverWithCard(Page page, Locator card, String jobKey) {
        try {
            Locator linkEl = card.locator("a[href]");
            if (linkEl.count() == 0) {
                return deliver(page, jobKey, null);
            }
            String href = linkEl.first().getAttribute("href");
            if (href == null) {
                return deliver(page, jobKey, null);
            }
            // 判断平台：智联 vs 猎聘
            String jobLink = href.startsWith("http") ? href : "https://www.liepin.com" + href;
            return deliver(page, jobKey, jobLink);
        } catch (Exception e) {
            return deliver(page, jobKey, null);
        }
    }

    private void safeSleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    /**
     * 投递完成后返回搜索列表页
     */
    private void navigateBackToListing(Page page) {
        try {
            String currentUrl = page.url();
            if (currentUrl.contains("/i") && (currentUrl.contains("zhaopin.com") || currentUrl.contains("liepin.com"))) {
                page.goBack(new Page.GoBackOptions().setTimeout(5000));
                safeSleep(1000);
            }
        } catch (Exception e) {
            log.debug("[DetailPageStrategy] navigateBack failed: {}", e.getMessage());
            try {
                page.navigate("https://www.zhaopin.com/sou/jl530/kw%E6%95%B0%E6%8D%AE/p1",
                    new Page.NavigateOptions().setTimeout(8000));
                safeSleep(1500);
            } catch (Exception ex) {
                log.debug("[DetailPageStrategy] fallback navigate failed: {}", ex.getMessage());
            }
        }
    }

    private String extractJobId(String link) {
        if (link == null) return "";
        try {
            Pattern p = Pattern.compile("/i(\\d+)\\.htm");
            Matcher m = p.matcher(link);
            if (m.find()) return m.group(1);
        } catch (Exception ignored) {}
        return "";
    }
}
