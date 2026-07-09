"""Async SQLAlchemy session/engine bootstrap."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logging import logger

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("DB session rolled back")
            raise


async def init_db() -> None:
    """Create tables (dev-only convenience). Use Alembic in prod."""
    from app.models import Base, Tenant, BillingAccount, User, Membership  # noqa: WPS433

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized at {}", settings.database_url)

    await _seed_default_tenant()
    await _ensure_tasks_tenant_id_column()


async def _ensure_tasks_tenant_id_column() -> None:
    """Ensure tasks.tenant_id column exists (backward compat for pre-alembic DBs).

    This is a safety net for dev SQLite DBs that were created before the
    alembic migration 0002_tenant_id ran. It is safe to call repeatedly.
    """
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("PRAGMA table_info(tasks)")
            )
            columns = [row[1] for row in result.fetchall()]
            if "tenant_id" not in columns:
                await conn.execute(
                    text("ALTER TABLE tasks ADD COLUMN tenant_id VARCHAR(64) DEFAULT 'default'")
                )
                await conn.commit()
                logger.info("tasks.tenant_id column added (startup fallback)")
    except Exception:
        # Non-blocking: if this fails (e.g. production DB managed by alembic),
        # the startup should still succeed.
        logger.warning("tasks.tenant_id column check failed (non-fatal)")


async def _seed_default_tenant() -> None:
    """Ensure a `default` tenant exists so single-tenant deployments keep working."""
    from app.models import BillingAccount, Membership, Tenant, User  # noqa: WPS433
    from sqlalchemy import select  # noqa: WPS433

    async with session_scope() as session:
        tid = settings.default_tenant_id
        tenant = await session.get(Tenant, tid)
        if tenant is None:
            tenant = Tenant(
                id=tid,
                name=settings.default_tenant_name,
                plan="free",
                status="active",
                seat_limit=1,
                monthly_post_quota=500,
            )
            session.add(tenant)
            await session.flush()
            billing = BillingAccount(tenant_id=tid)
            session.add(billing)
            logger.info("Seeded default tenant: id={} plan=free", tid)

        # Optional bootstrap admin user (BOOTSTRAP_ADMIN_EMAIL / PASSWORD)
        if settings.bootstrap_admin_email and settings.bootstrap_admin_password:
            from app.core.security import hash_password  # noqa: WPS433

            existing = (
                await session.execute(select(User).where(User.email == settings.bootstrap_admin_email))
            ).scalar_one_or_none()
            if existing is None:
                admin = User(
                    email=settings.bootstrap_admin_email,
                    password_hash=hash_password(settings.bootstrap_admin_password),
                    display_name="Bootstrap Admin",
                    is_superadmin=True,
                    status="active",
                )
                session.add(admin)
                await session.flush()
                session.add(Membership(user_id=admin.id, tenant_id=tid, role="owner"))
                logger.info("Seeded bootstrap admin: email={}", admin.email)