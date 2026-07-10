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
            if task.ai_mode == "agent":
                content = await factory.agent_rewrite(task, content, persona=task.ai_persona)
            else:
                content = await factory.maybe_rewrite(content, persona=task.ai_persona)

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