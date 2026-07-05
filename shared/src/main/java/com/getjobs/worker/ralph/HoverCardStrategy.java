package com.getjobs.worker.ralph;

import com.microsoft.playwright.Page;
import com.microsoft.playwright.Locator;
import com.microsoft.playwright.ElementHandle;
import com.microsoft.playwright.options.BoundingBox;
import com.microsoft.playwright.options.WaitUntilState;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/**
 * 策略1: 卡片悬停投递
 * hover 触发懒加载按钮后直接点击
 */
@Slf4j
@Component
public class HoverCardStrategy implements DeliveryStrategy {

    private static final long HOVER_WAIT_MS = 2000L;
    private static final long POST_CLICK_WAIT_MS = 800L;

    private static final String[] BUTTON_SELECTORS = {
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
            // 猎聘选择器：聊一聊 / 立即沟通
            "button:has-text('聊一聊')",
            "a:has-text('聊一聊')",
            "button:has-text('立即沟通')",
            "a:has-text('立即沟通')",
            "[class*='liao'] button",
            "[class*='liao'] a",
            "[class*='chat-im'] button",
            "[class*='chat-im'] a",
            "[class*='im-chat'] button",
            "[class*='im-chat'] a",
            "[class*='chat'] button",
            "[class*='chat'] a"
    };

    @Override
    public String name() {
        return "hover_card";
    }

    @Override
    public int priority() {
        return 1;
    }

    @Override
    public boolean canHandle(RalphFailureDiagnosis diagnosis) {
        return diagnosis == null
                || diagnosis.getPattern().isEmpty()
                || diagnosis.getPattern().equals("unknown_error")
                || diagnosis.getPattern().equals("companydetail_redirect");
    }

    @Override
    public DeliveryResult deliver(Page page, String jobKey, String jobLink) {
        // 优先用传入的 jobLink 匹配卡片，否则在列表中搜索
        if (jobLink != null && !jobLink.isBlank()) {
            return deliverByLink(page, jobKey, jobLink);
        }
        return deliverBySearch(page, jobKey);
    }

    /**
     * 通过 jobLink 直接定位卡片
     */
    private DeliveryResult deliverByLink(Page page, String jobKey, String jobLink) {
        try {
            String jobId = extractJobId(jobLink);
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
                    Locator linkEl = card.locator("a[href]");
                    if (linkEl.count() > 0) {
                        String href = linkEl.first().getAttribute("href");
                        if (href != null && (href.contains(jobId) || href.contains(jobLink))) {
                            return attemptDeliveryOnCard(page, card);
                        }
                    }
                } catch (Exception ignored) {}
            }
            return deliverBySearch(page, jobKey);
        } catch (Exception e) {
            return DeliveryResult.failed("hover_card_exception", e.getMessage());
        }
    }

    private String extractJobId(String link) {
        if (link == null) return null;
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("/i(\\d+)\\.htm").matcher(link);
        return m.find() ? m.group(1) : null;
    }

    /**
     * 在列表中搜索匹配岗位
     */
    private DeliveryResult deliverBySearch(Page page, String jobKey) {
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

            int cardCount = cards.count();
            if (cardCount == 0) {
                return DeliveryResult.failed("element_not_found", "找不到岗位卡片列表");
            }

            String keyword = jobKey.contains("_")
                    ? jobKey.split("_")[1].trim()
                    : jobKey;

            for (int i = 0; i < cardCount; i++) {
                Locator card = cards.nth(i);
                String cardTitle = "";
                try {
                    var titleEl = card.locator(
                            "div.jobinfo__name, [class*='jobinfo__name'], " +
                            "[class*='job-name'], a[class*='name'], span[class*='name']"
                    );
                    if (titleEl.count() > 0) {
                        cardTitle = titleEl.first().textContent();
                    }
                } catch (Exception ignored) {}

                if (cardTitle != null && !cardTitle.isBlank()) {
                    String ct = cardTitle.trim();
                    String kw = keyword.trim();
                    // 精确匹配：cardTitle 是 jobKey 的子串，或完全相等（避免 "Java" 匹配 "JavaScript"）
                    if (ct.contains(kw) && kw.length() >= 2) {
                        return attemptDeliveryOnCard(page, card);
                    }
                }
            }

            return DeliveryResult.failed("element_not_found", "在列表中找不到岗位: " + jobKey);

        } catch (Exception e) {
            return DeliveryResult.failed("exception", e.getMessage());
        }
    }

    @Override
    public DeliveryResult deliverWithCard(Page page, Locator card, String jobKey) {
        return attemptDeliveryOnCard(page, card);
    }

    private DeliveryResult attemptDeliveryOnCard(Page page, Locator card) {
        // 关闭可能存在的弹窗
        closeAllModals(page);

        // 滚动到卡片并触发鼠标事件（智联反爬升级）
        try {
            com.microsoft.playwright.ElementHandle eh = card.elementHandle();
            if (eh != null) {
                eh.evaluate("(el) => { " +
                        "el.scrollIntoViewIfNeeded(); " +
                        "el.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true})); " +
                        "el.dispatchEvent(new MouseEvent('mouseover', {bubbles: true})); " +
                        "}");
            }
        } catch (Exception ignored) {}
        try { card.hover(); } catch (Exception e) { log.debug("hover failed: {}", e.getMessage()); }
        safeSleep(1500);

        // 关闭 hover 后出现的遮罩
        closeAllModals(page);

        // 阶段 A：列表页 inline 点击
        DeliveryResult result = tryClickInlineButtonFromListPage(page, card);
        if (result != null) return result;

        // 阶段 B：点击卡片跳详情页（用短超时，避免等导航）
        try {
            int pagesBefore = page.context().pages().size();
            // 不等待导航，只等点击完成（最多 5s）
            card.click(new Locator.ClickOptions().setTimeout(5000));
            safeSleep(1500);
            closePopupTabs(page);
            // 检查是否开了新标签页
            if (page.context().pages().size() > pagesBefore) {
                Page target = page.context().pages().get(page.context().pages().size() - 1);
                safeSleep(1000);
                DeliveryResult r = tryDeliverOnDetailPage(target);
                target.close();
                return r;
            }
            // 没开新标签，直接在当前页尝试详情页投递
            return tryDeliverOnDetailPage(page);
        } catch (Exception e) {
            log.debug("card click failed: {}", e.getMessage());
            return DeliveryResult.failed("button_not_clickable", e.getMessage());
        }
    }

    private void closeAllModals(Page page) {
        try {
            page.evaluate("() => { " +
                    "document.querySelectorAll('.a-modal, [class*=\"modal\"], [class*=\"mask\"], " +
                    "[class*=\"overlay\"], [class*=\"popup\"], [class*=\"dialog\"]').forEach(el => { " +
                    "  try { el.remove(); } catch(e){} " +
                    "}); " +
                    "}");
            safeSleep(100);
        } catch (Exception ignored) {}
    }

    /**
     * 两阶段流程：列表页 inline "立即投递"按钮优先，失败再 fallback 到详情页。
     * 阶段 A：在 page 维度（不是 card 子树）查 BUTTON_SELECTORS，过滤出落在卡片矩形内的按钮；
     *        命中后三段式点击（normal -> JS -> force），命中即返回 SUCCESS（停留列表页）。
     * 阶段 B：阶段 A 失败后 card.click() 跳详情页，调用 tryDeliverOnDetailPage。
     *        命中返回 SUCCESS；失败返回 DeliveryResult.failed("button_not_clickable", ...)。
     */
    private DeliveryResult tryClickButtonFromPage(Page page, Locator card) {
        // ====== 阶段 A：列表页 inline "立即投递"按钮 ======
        DeliveryResult stageAResult = tryClickInlineButtonFromListPage(page, card);
        if (stageAResult != null) return stageAResult;

        // ====== 阶段 B：fallback 到详情页 ======
        try {
            card.click(new Locator.ClickOptions().setTimeout(5000));
            safeSleep(2000);
            return tryDeliverOnDetailPage(page);
        } catch (Exception e) {
            log.debug("tryClickButtonFromPage card click failed: {}", e.getMessage());
            return DeliveryResult.failed("button_not_clickable", e.getMessage());
        }
    }

    /**
     * 阶段 A：在列表页直接点击卡片内联的"立即投递"按钮。
     * 混合策略：先用 page.locator() (支持 :has-text 等 Playwright 专有选择器) 找所有候选按钮，
     * 再在 Java 侧过滤出落在卡片矩形内的那个。
     */
    private DeliveryResult tryClickInlineButtonFromListPage(Page page, Locator card) {
        BoundingBox cardBox = null;
        try {
            cardBox = card.boundingBox();
        } catch (Exception ignored) {}
        if (cardBox == null) {
            log.debug("[列表页 inline 投递] 拿不到卡片 boundingBox，跳过阶段 A");
            return null;
        }
        final double cx = cardBox.x;
        final double cy = cardBox.y;
        final double cw = cardBox.width;
        final double ch = cardBox.height;
        final double x2 = cx + cw;
        final double y2 = cy + ch;

        long stageADeadline = System.currentTimeMillis() + 5000L;
        int[] retryDelays = {200, 500, 1000};
        int delayIdx = 0;

        // 所有候选选择器（支持 Playwright 专有 :has-text）
        String[] allCandidateSelectors = {
            "button.collect-and-apply__btn",
            "button:has-text('立即投递')", "a:has-text('立即投递')",
            "button:has-text('投递')", "a:has-text('投递')",
            "span:has-text('立即投递')", "span:has-text('投递')",
            "button[class*='apply']", "a[class*='apply']",
            "[class*='deliver']", "[class*='collect-and-apply']",
            ".btn-apply", ".apply-btn", "button.btn-primary", "a.btn-primary",
            ".job-apply-button", "[class*='submit']",
            ".job-detail-btn button", ".resume-container button", ".apply-container button",
            "[data-action='apply']", "[data-type='apply']",
            "button[class*='action']", "a[class*='action']",
            "[class*='apply'] button"
        };

        while (System.currentTimeMillis() < stageADeadline) {
            if (delayIdx < retryDelays.length) {
                safeSleep(retryDelays[delayIdx]);
                delayIdx++;
            } else {
                safeSleep(400);
            }

            // 遍历所有选择器
            Locator foundBtn = null;
            String foundText = "";
            for (String sel : allCandidateSelectors) {
                try {
                    Locator candidates = page.locator(sel);
                    int cnt = candidates.count();
                    for (int b = 0; b < cnt; b++) {
                        BoundingBox bb = candidates.nth(b).boundingBox();
                        if (bb == null) continue;
                        // 判断是否落在卡片矩形内
                        if (bb.x < cx - 5 || bb.y < cy - 5 || (bb.x + bb.width) > x2 + 5 || (bb.y + bb.height) > y2 + 5) continue;

                        String text = "";
                        try { text = candidates.nth(b).textContent(); } catch (Exception ignored) {}
                        if (text != null && (text.contains("已投递") || text.contains("已申请") || text.contains("投递成功"))) continue;

                        boolean disabled = false;
                        try { disabled = candidates.nth(b).isDisabled(); } catch (Exception ignored) {}

                        if (!disabled) {
                            foundBtn = candidates.nth(b);
                            foundText = text != null ? text.trim() : "";
                            log.info("[列表页 inline 投递] sel={} text='{}' box=({},{:.0f},{:.0f},{:.0f},{:.0f})",
                                    sel, foundText.length() > 20 ? foundText.substring(0, 20) : foundText,
                                    (int)bb.x, (int)bb.y, (int)(bb.x + bb.width), (int)(bb.y + bb.height));
                            break;
                        }
                    }
                } catch (Exception e) {
                    log.debug("[列表页 inline] selector '{}' error: {}", sel, e.getMessage());
                }
                if (foundBtn != null) break;
            }

            if (foundBtn == null) continue;

            // 尝试 1：正常 click
            try {
                foundBtn.click(new Locator.ClickOptions().setTimeout(2000));
                safeSleep(800);
                if (isPageShowingDeliverySuccess(page)) {
                    log.info("[列表页 inline 投递] 命中（normal click）");
                    return DeliveryResult.success(name());
                }
            } catch (Exception ignored) {}

            // 尝试 2：JS click
            try {
                foundBtn.evaluate("el => el.click()");
                safeSleep(800);
                if (isPageShowingDeliverySuccess(page)) {
                    log.info("[列表页 inline 投递] 命中（js click）");
                    return DeliveryResult.success(name());
                }
            } catch (Exception ignored) {}

            // 尝试 3：force click
            try {
                foundBtn.click(new Locator.ClickOptions().setForce(true).setTimeout(2000));
                safeSleep(800);
                if (isPageShowingDeliverySuccess(page)) {
                    log.info("[列表页 inline 投递] 命中（force click）");
                    return DeliveryResult.success(name());
                }
            } catch (Exception ignored) {}

            // 三个 click 都未触发 success：可能弹窗异步，再等 1.2s
            safeSleep(1200);
            if (isPageShowingDeliverySuccess(page)) {
                log.info("[列表页 inline 投递] 命中（异步弹窗）");
                return DeliveryResult.success(name());
            }
            log.debug("[列表页 inline 投递] 三段式未命中，循环重试");
        }
        log.debug("[列表页 inline 投递] 阶段 A 超时/未命中，fallback 到详情页");
        return null;
    }

    /**
     * 详情页找聊一聊并投递
     */
    private DeliveryResult tryDeliverOnDetailPage(Page page) {
        // 检查是否已投递
        if (isPageShowingDeliverySuccess(page)) {
            navigateBack(page);
            return DeliveryResult.alreadyDelivered();
        }

        // 检查是否被重定向
        if (isRedirectedToUnexpectedPage(page)) {
            navigateBack(page);
            return DeliveryResult.failed("companydetail_redirect", "详情页被重定向");
        }

        // 详情页专属选择器（聊一聊、立即沟通、立即投递等）
        String[] detailSelectors = {
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

        for (String sel : detailSelectors) {
            try {
                Locator btn = page.locator(sel);
                if (btn.count() == 0) continue;

                // 直接 force 点击（跳过 enabled/intercept 检查，避免 30 秒阻塞）
                try {
                    page.evaluate("() => document.querySelectorAll('.a-modal.a-job-apply-workflow-close').forEach(el => el.click())");
                    safeSleep(150);
                } catch (Exception ignored) {}
                btn.first().scrollIntoViewIfNeeded();
                btn.first().click(new Locator.ClickOptions().setForce(true).setTimeout(3000));
                safeSleep(POST_CLICK_WAIT_MS);
                closePopupTabs(page);
                if (isPageShowingDeliverySuccess(page)) {
                    navigateBack(page);
                    return DeliveryResult.success(name());
                }
            } catch (Exception e) {
                log.debug("DetailPage chat btn sel '{}' failed: {}", sel, e.getMessage());
            }
        }

        navigateBack(page);
        return DeliveryResult.failed("button_not_clickable", "详情页找不到聊一聊按钮");
    }

    private void navigateBack(Page page) {
        try {
            if (!isOnSearchListPage(page)) {
                page.goBack(new Page.GoBackOptions().setTimeout(5000));
                safeSleep(1000);
            }
        } catch (Exception e) {
            log.debug("[HoverCard] navigateBack failed: {}", e.getMessage());
            // 最后手段：导航到搜索页
            try {
                page.navigate("https://www.zhaopin.com/sou/jl530/kw%E6%95%B0%E6%8D%AE/p1",
                    new Page.NavigateOptions().setTimeout(10000));
                safeSleep(2000);
            } catch (Exception ex) {
                log.debug("[HoverCard] fallback navigate failed: {}", ex.getMessage());
            }
        }
    }

    private void safeSleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

}
