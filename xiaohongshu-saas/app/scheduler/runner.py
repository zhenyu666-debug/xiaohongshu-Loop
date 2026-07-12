"""Job orchestration: load a task, build content, run risk-check, dispatch to channel."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.channels import registry
from app.content_factory import factory
from app.core.logging import logger
from app.core import metrics
from app.core.risk import evaluate as risk_evaluate
from app.core.risk import mark_failure, mark_success
from app.core.types import ContentItem, PublishResult, PublishStatus
from app.models import Account, Content, Publish, Task


async def run_task_once(session: AsyncSession, task: Task) -> list[Publish]:
    """Materialise one iteration of a task across all enabled accounts.

    Returns the list of Publish rows created (status will already be set).
    """
    template = factory.load_template(task.template_key)
    publishes: list[Publish] = []

    if not task.account_ids:
        logger.warning("task {} has no accounts bound", task.id)
        return publishes

    for account_id in task.account_ids:
        account = await session.get(Account, account_id)
        if not account or not account.enabled:
            logger.info("skip account {} (missing/disabled)", account_id)
            continue

        verdict = await risk_evaluate(session, account)
        if not verdict.allowed:
            logger.info("skip account {} (risk: {})", account_id, verdict.reason)
            metrics.inc("risk_blocks_total", account_id=account_id, reason=verdict.reason[:64])
            publishes.append(await _record_skipped(session, task, account, verdict.reason))
            continue

        content = factory.render(template)
        if task.use_ai:
            content = await _apply_ai_rewrite(task, content)

        # Persist content for audit
        content_row = Content(
            account_id=account.id,
            template_key=template.key,
            title=content.title,
            body=content.body,
            payload={
                "images": content.images,
                "video": content.video,
                "topics": content.topics,
                "extra": content.extra,
            },
        )
        session.add(content_row)
        await session.flush()

        publish_row = Publish(
            task_id=task.id,
            account_id=account.id,
            channel=task.channel,
            status=PublishStatus.RUNNING.value,
            title=content.title,
            started_at=datetime.utcnow(),
        )
        session.add(publish_row)
        await session.flush()

        adapter = registry.get(task.channel)
        try:
            result: PublishResult = await adapter.publish(account, content)
        except Exception as exc:  # noqa: BLE001
            result = PublishResult(success=False, error=str(exc))

        publish_row.finished_at = datetime.utcnow()
        if result.success:
            publish_row.status = PublishStatus.SUCCESS.value
            publish_row.external_id = result.external_id
            publish_row.url = result.url
            await mark_success(session, account)
            metrics.inc("publishes_total", channel=task.channel, status="success")
        else:
            publish_row.status = PublishStatus.FAILED.value
            publish_row.error = result.error or "unknown"
            await mark_failure(session, account, publish_row.error or "unknown")
            metrics.inc("publishes_total", channel=task.channel, status="failed")

        publishes.append(publish_row)

    task.last_run_at = datetime.utcnow()
    await session.commit()
    return publishes


async def _record_skipped(session: AsyncSession, task: Task, account: Account, reason: str) -> Publish:
    row = Publish(
        task_id=task.id,
        account_id=account.id,
        channel=task.channel,
        status=PublishStatus.SKIPPED.value,
        error=reason,
        finished_at=datetime.utcnow(),
    )
    session.add(row)
    await session.flush()
    metrics.inc("publishes_total", channel=task.channel, status="skipped")
    return row


async def _apply_ai_rewrite(task: Task, content: ContentItem) -> ContentItem:
    """Dispatch on ``task.ai_mode`` to the matching factory function.

    Defensive contract:
        * If the factory raises (e.g. ``factory.agent_rewrite`` ever stops
          swallowing exceptions internally), the exception is logged here and
          the template-rendered ``content`` is returned untouched so the
          publish loop still records ``task.last_run_at`` at the end of
          ``run_task_once``.
        * Unknown ``ai_mode`` values fall back to ``maybe_rewrite`` and emit a
          warning, rather than silently passing through as the previous bare
          ``else`` did.
    """
    mode = (task.ai_mode or "rewrite").lower()
    persona = task.ai_persona

    try:
        if mode == "agent":
            return await factory.agent_rewrite(task, content, persona=persona)
        if mode == "rewrite":
            return await factory.maybe_rewrite(content, persona=persona)
    except Exception:  # noqa: BLE001
        logger.exception(
            "AI rewrite failed in scheduler; falling back to template content (task_id={}, mode={})",
            task.id,
            mode,
        )
        return content

    logger.warning(
        "Unknown task.ai_mode={!r}; falling back to rewrite path (task_id={})",
        task.ai_mode,
        task.id,
    )
    try:
        return await factory.maybe_rewrite(content, persona=persona)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Rewrite fallback failed for unknown ai_mode; returning raw content (task_id={})",
            task.id,
        )
        return content