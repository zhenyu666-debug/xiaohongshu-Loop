"""Account management endpoints.

All endpoints are tenant-scoped: accounts belong to the caller's tenant
and the `tenant_id` is automatically applied to create/read/update.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels import registry
from app.core.auth import Principal, current_principal, record_audit
from app.db.session import get_session
from app.models import Account
from app.schemas import AccountCreate, AccountOut

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
async def list_accounts(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[Account]:
    result = await session.execute(
        select(Account).where(Account.tenant_id == principal.tenant.id).order_by(Account.created_at.desc())
    )
    return list(result.scalars())


@router.post("", response_model=AccountOut, status_code=201)
async def create_account(
    payload: AccountCreate,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> Account:
    exists = await session.get(Account, payload.id)
    if exists:
        raise HTTPException(409, f"account {payload.id} already exists")
    account = Account(
        id=payload.id,
        tenant_id=principal.tenant.id,
        channel=payload.channel,
        nickname=payload.nickname,
        proxy=payload.proxy,
        persona=payload.persona,
        enabled=payload.enabled,
    )
    session.add(account)
    await record_audit(session, principal, action="account.create", resource="account", resource_id=account.id)
    await session.commit()
    await session.refresh(account)
    return account


@router.delete("/{account_id}", status_code=204)
async def delete_account(
    account_id: str,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    account = await session.get(Account, account_id)
    if not account or account.tenant_id != principal.tenant.id:
        raise HTTPException(404, "not found")
    await session.delete(account)
    await record_audit(session, principal, action="account.delete", resource="account", resource_id=account_id)
    await session.commit()


@router.post("/{account_id}/login", status_code=202)
async def login_account(
    account_id: str,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    account = await session.get(Account, account_id)
    if not account or account.tenant_id != principal.tenant.id:
        raise HTTPException(404, "not found")
    adapter = registry.get(account.channel)
    await adapter.login(account)
    account.cookie_path = adapter.cookie_path_for(account.id) if hasattr(adapter, "cookie_path_for") else None
    account.stage = "warmup"
    await record_audit(session, principal, action="account.login", resource="account", resource_id=account_id)
    await session.commit()
    return {"status": "logged in", "account_id": account_id, "cookie_path": account.cookie_path}


@router.post("/{account_id}/heartbeat")
async def heartbeat_account(
    account_id: str,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    account = await session.get(Account, account_id)
    if not account or account.tenant_id != principal.tenant.id:
        raise HTTPException(404, "not found")
    adapter = registry.get(account.channel)
    health = await adapter.heartbeat(account)
    return health.model_dump()