from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
import httpx
import json
import re

from pydantic import BaseModel

from sqlmodel import select

from ..ai.factory import get_provider
from ..ai.openai_compatible_client import run_openai_compatible
from ..db import get_session
from ..deps import get_current_user, get_optional_user
from ..models import Document, DocumentVersion, Task, TaskStatus, User, UserAIConfig, UserAPIKey
from ..queue import enqueue_task
from ..settings import settings
from ..text import read_version_text

router = APIRouter(prefix="/ai", tags=["ai"])

logger = logging.getLogger(__name__)


def _truncate_for_http_detail(text: str, limit: int = 1000) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[:limit] + "…"


def _openrouter_exception_detail(exc: Exception) -> str:
    # Keep details useful but safe: no headers, no tokens.
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        body = _truncate_for_http_detail(exc.response.text)
        return f"HTTP {status}: {body}" if body else f"HTTP {status}"
    if isinstance(exc, httpx.RequestError):
        return f"Request error: {exc}"
    msg = str(exc).strip()
    return _truncate_for_http_detail(msg) if msg else exc.__class__.__name__


class SummarizeRequest(BaseModel):
    version_id: str
    instructions: Optional[str] = None


class CompareRequest(BaseModel):
    left_version_id: str
    right_version_id: str
    instructions: Optional[str] = None


class TranslateBilingualRequest(BaseModel):
    version_id: str
    source_lang: str = "ru"
    target_lang: str = "en"


class AIResult(BaseModel):
    text: str
    task_id: Optional[str] = None


class GenerateTemplateRequest(BaseModel):
    base_text: Optional[str] = None
    instructions: Optional[str] = None
    entities: dict[str, Any] = {}


class ExtractEntitiesRequest(BaseModel):
    version_id: str
    instructions: Optional[str] = None


class ExtractEntitiesResponse(BaseModel):
    data: dict[str, Any]
    raw_text: str


class OpenRouterModel(BaseModel):
    id: str
    name: Optional[str] = None
    context_length: Optional[int] = None


class OpenRouterConfigResponse(BaseModel):
    provider: str
    base_url: str
    model: Optional[str] = None
    has_api_key: bool
    active_key_id: Optional[str] = None
    keys_count: int = 0


class OpenRouterConfigUpdateRequest(BaseModel):
    # If provided, stored as a new user key and becomes active.
    api_key: Optional[str] = None
    label: Optional[str] = None
    # Alternatively, select an existing key by id.
    active_key_id: Optional[str] = None
    model: Optional[str] = None


class OpenRouterKeyItem(BaseModel):
    id: str
    label: Optional[str] = None
    created_at: datetime
    is_active: bool


class OpenRouterKeyCreateRequest(BaseModel):
    api_key: str
    label: Optional[str] = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    version_id: Optional[str] = None


class ChatResponse(BaseModel):
    text: str


def _get_user_openrouter_config(session, user_id: str) -> Optional[UserAIConfig]:
    return session.exec(
        select(UserAIConfig)
        .where(UserAIConfig.user_id == user_id)
        .where(UserAIConfig.provider == "openrouter")
        .limit(1)
    ).first()


def _get_user_openrouter_keys(session, user_id: str) -> list[UserAPIKey]:
    return list(
        session.exec(
            select(UserAPIKey)
            .where(UserAPIKey.user_id == user_id)
            .where(UserAPIKey.provider == "openrouter")
            .order_by(UserAPIKey.created_at.desc())
        ).all()
    )


def _maybe_migrate_legacy_openrouter_key(session, user: User, cfg: Optional[UserAIConfig]) -> Optional[UserAIConfig]:
    if not cfg:
        return None
    if cfg.api_key_id:
        return cfg
    legacy = (cfg.api_key or "").strip()
    if not legacy:
        return cfg

    key = UserAPIKey(
        user_id=user.id,
        provider="openrouter",
        label="imported",
        api_key=legacy,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(key)
    session.commit()
    session.refresh(key)

    cfg.api_key_id = key.id
    cfg.api_key = ""
    cfg.updated_at = datetime.utcnow()
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return cfg


def _get_openrouter_runtime(session, user: User) -> Optional[tuple[str, str, str]]:
    cfg = _get_user_openrouter_config(session, user.id)
    cfg = _maybe_migrate_legacy_openrouter_key(session, user, cfg)
    if not cfg:
        return None

    model = (cfg.model or "").strip()
    if not model:
        return None

    api_key = ""
    if cfg.api_key_id:
        k = session.get(UserAPIKey, cfg.api_key_id)
        if k and k.user_id == user.id and k.provider == "openrouter":
            api_key = (k.api_key or "").strip()
    if not api_key:
        api_key = (cfg.api_key or "").strip()

    if not api_key:
        return None

    return (cfg.base_url, api_key, model)


@router.get("/openrouter/models")
async def openrouter_models() -> list[OpenRouterModel]:
    import httpx

    url = "https://openrouter.ai/api/v1/models"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json() or {}

    items = data.get("data")
    if not isinstance(items, list):
        return []

    out: list[OpenRouterModel] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        mid = it.get("id")
        if not isinstance(mid, str) or not mid:
            continue
        out.append(
            OpenRouterModel(
                id=mid,
                name=it.get("name") if isinstance(it.get("name"), str) else None,
                context_length=it.get("context_length") if isinstance(it.get("context_length"), int) else None,
            )
        )
    return out


@router.get("/openrouter/config")
def get_openrouter_config(user: User = Depends(get_current_user)) -> OpenRouterConfigResponse:
    with get_session() as session:
        cfg = _get_user_openrouter_config(session, user.id)
        cfg = _maybe_migrate_legacy_openrouter_key(session, user, cfg)
        keys = _get_user_openrouter_keys(session, user.id)

        if not cfg:
            return OpenRouterConfigResponse(
                provider="openrouter",
                base_url="https://openrouter.ai/api/v1",
                model=None,
                has_api_key=False,
                active_key_id=None,
                keys_count=len(keys),
            )

        has_key = bool(_get_openrouter_runtime(session, user))
        return OpenRouterConfigResponse(
            provider=cfg.provider,
            base_url=cfg.base_url,
            model=cfg.model,
            has_api_key=has_key,
            active_key_id=cfg.api_key_id,
            keys_count=len(keys),
        )


@router.put("/openrouter/config")
def update_openrouter_config(
    req: OpenRouterConfigUpdateRequest,
    user: User = Depends(get_current_user),
) -> OpenRouterConfigResponse:
    api_key = (req.api_key or "").strip()
    label = (req.label or "").strip() or None
    active_key_id = (req.active_key_id or "").strip() or None
    model = (req.model or "").strip() or None

    with get_session() as session:
        cfg = _get_user_openrouter_config(session, user.id)
        cfg = _maybe_migrate_legacy_openrouter_key(session, user, cfg)

        if not cfg:
            cfg = UserAIConfig(
                user_id=user.id,
                provider="openrouter",
                base_url="https://openrouter.ai/api/v1",
                api_key="",
                api_key_id=None,
                model=model or "",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(cfg)
            session.commit()
            session.refresh(cfg)

        if api_key:
            k = UserAPIKey(
                user_id=user.id,
                provider="openrouter",
                label=label,
                api_key=api_key,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(k)
            session.commit()
            session.refresh(k)
            cfg.api_key_id = k.id
            cfg.api_key = ""

        if active_key_id:
            k2 = session.get(UserAPIKey, active_key_id)
            if not k2 or k2.user_id != user.id or k2.provider != "openrouter":
                raise HTTPException(status_code=404, detail="API key not found")
            cfg.api_key_id = k2.id
            cfg.api_key = ""

        if model is not None:
            cfg.model = model

        cfg.updated_at = datetime.utcnow()
        session.add(cfg)
        session.commit()
        session.refresh(cfg)

        keys = _get_user_openrouter_keys(session, user.id)
        has_key = bool(_get_openrouter_runtime(session, user))
        return OpenRouterConfigResponse(
            provider=cfg.provider,
            base_url=cfg.base_url,
            model=cfg.model,
            has_api_key=has_key,
            active_key_id=cfg.api_key_id,
            keys_count=len(keys),
        )


@router.get("/openrouter/keys")
def list_openrouter_keys(user: User = Depends(get_current_user)) -> list[OpenRouterKeyItem]:
    with get_session() as session:
        cfg = _get_user_openrouter_config(session, user.id)
        cfg = _maybe_migrate_legacy_openrouter_key(session, user, cfg)
        active_id = cfg.api_key_id if cfg else None
        keys = _get_user_openrouter_keys(session, user.id)
        return [
            OpenRouterKeyItem(
                id=k.id,
                label=k.label,
                created_at=k.created_at,
                is_active=(k.id == active_id),
            )
            for k in keys
        ]


@router.post("/openrouter/keys")
def create_openrouter_key(req: OpenRouterKeyCreateRequest, user: User = Depends(get_current_user)) -> OpenRouterKeyItem:
    api_key = (req.api_key or "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key is required")
    label = (req.label or "").strip() or None

    with get_session() as session:
        k = UserAPIKey(
            user_id=user.id,
            provider="openrouter",
            label=label,
            api_key=api_key,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(k)
        session.commit()
        session.refresh(k)

        cfg = _get_user_openrouter_config(session, user.id)
        cfg = _maybe_migrate_legacy_openrouter_key(session, user, cfg)
        if not cfg:
            cfg = UserAIConfig(
                user_id=user.id,
                provider="openrouter",
                base_url="https://openrouter.ai/api/v1",
                api_key="",
                api_key_id=k.id,
                model="",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(cfg)
        else:
            cfg.api_key_id = k.id
            cfg.api_key = ""
            cfg.updated_at = datetime.utcnow()
            session.add(cfg)
        session.commit()

        return OpenRouterKeyItem(id=k.id, label=k.label, created_at=k.created_at, is_active=True)


@router.delete("/openrouter/keys/{key_id}")
def delete_openrouter_key(key_id: str, user: User = Depends(get_current_user)) -> dict[str, bool]:
    with get_session() as session:
        k = session.get(UserAPIKey, key_id)
        if not k or k.user_id != user.id or k.provider != "openrouter":
            raise HTTPException(status_code=404, detail="API key not found")

        cfg = _get_user_openrouter_config(session, user.id)
        cfg = _maybe_migrate_legacy_openrouter_key(session, user, cfg)

        session.delete(k)
        session.commit()

        if cfg and cfg.api_key_id == key_id:
            remaining = _get_user_openrouter_keys(session, user.id)
            cfg.api_key_id = remaining[0].id if remaining else None
            cfg.updated_at = datetime.utcnow()
            session.add(cfg)
            session.commit()

        return {"ok": True}


@router.post("/extract-entities")
async def extract_entities(
    req: ExtractEntitiesRequest,
    user: User = Depends(get_current_user),
) -> ExtractEntitiesResponse:
    version = _get_version_or_404(req.version_id, user_id=user.id)
    source = read_version_text(version)

    system = (
        "You extract structured entity fields from Russian legal/contract documents. "
        "Return ONLY valid JSON (no markdown, no comments). "
        "Keys must be in snake_case matching the provided schema. "
        "Unknown keys must be omitted. "
        "If a value is unknown, omit the key (do not guess)."
    )

    schema = {
        # Parties
        "customer_status": "person|ip|self_employed|company",
        "customer_fio": "string",
        "customer_address": "string",
        "customer_phone": "string",
        "customer_email": "string",
        "customer_inn": "string",
        "customer_telegram": "string",
        "customer_whatsapp": "string",
        "executor_name": "string",
        "executor_address": "string",
        "executor_inn": "string",
        "executor_phone": "string",
        "executor_email": "string",
        "executor_telegram": "string",
        # Object
        "object_address": "string",
        "object_country": "string",
        "object_city": "string",
        "object_house": "string",
        "object_entrance": "string",
        "object_apartment": "string",
        "object_type": "apartment|house|commercial|other",
        "object_rooms_count": "string",
        "object_area_sqm": "string",
        "object_ceiling_height_m": "string",
        "object_floor": "string",
        "object_floors_total": "string",
        "object_bathrooms_count": "string",
        "object_has_balcony": "no|yes",
        "object_rooms_list": "string",
        "object_residents_count": "string",
        "object_has_pets": "no|yes",
        "object_pets_notes": "string",
        # Project
        "project_scope": "full|rooms_only|consultation|other",
        "project_style": "string",
        "project_renovation_type": "new_build|secondary|cosmetic|capital|other",
        "project_budget": "string",
        "project_deadline": "string",
        "project_notes": "string",
        "project_price": "string",
        "project_price_per_sqm": "string",
        "project_price_total": "string",
        "project_payment_terms": "string",
        "payment_method_cash": "boolean",
        "payment_method_bank_transfer": "boolean",
        "payment_method_card": "boolean",
        "payment_method_sbp": "boolean",
        "payment_method_other": "string",
        "project_revisions_included": "string",
        "project_revision_extra_terms": "string",
        "project_author_supervision": "no|yes",
        "project_site_visits_count": "string",
        "project_site_visits_paid_by": "customer|executor|split|other",
        "project_site_visits_paid_by_details": "string",
        "project_site_visits_expenses": "string",
        "project_procurement_buys_paid_by": "customer|executor|split|other",
        "project_procurement_buys_details": "string",
        "project_procurement_delivery_acceptance_by": "customer|executor|split|other",
        "project_procurement_delivery_acceptance_details": "string",
        "project_procurement_lifting_assembly_paid_by": "customer|executor|split|other",
        "project_procurement_lifting_assembly_details": "string",
        "project_procurement_storage_paid_by": "customer|executor|split|other",
        "project_procurement_storage_details": "string",
        "project_approval_sla": "string",
        "project_deadline_shift_terms": "string",
        "project_penalties_terms": "string",
        "project_handover_format": "string",
        "project_communication_channel": "telegram|whatsapp|email|phone|other",
        "project_communication_details": "string",
        "project_communication_rules": "string",
        # Deliverables
        "deliverable_measurements": "boolean",
        "deliverable_plan_solution": "boolean",
        "deliverable_demolition_plan": "boolean",
        "deliverable_construction_plan": "boolean",
        "deliverable_electric_plan": "boolean",
        "deliverable_plumbing_plan": "boolean",
        "deliverable_lighting_plan": "boolean",
        "deliverable_ceiling_plan": "boolean",
        "deliverable_floor_plan": "boolean",
        "deliverable_furniture_plan": "boolean",
        "deliverable_finishes_schedule": "boolean",
        "deliverable_specification": "boolean",
        "deliverable_3d_visuals": "boolean",
    }

    user_parts = [
        "Extract entity fields from the document. Output JSON object with any subset of keys.",
        "Schema (key -> type/enum):\n" + json.dumps(schema, ensure_ascii=False, indent=2),
    ]

    if req.instructions:
        user_parts.append("Extra instructions:\n" + req.instructions)

    user_parts.append("Document text:\n" + source)

    user_prompt = "\n\n---\n\n".join(user_parts)

    with get_session() as session:
        rt = _get_openrouter_runtime(session, user)

    if rt:
        base_url, api_key, model = rt
        try:
            resp = await run_openai_compatible(
                base_url=base_url,
                api_key=api_key,
                model=model,
                system=system,
                user=user_prompt,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"OpenRouter config error: {e}") from e
        except Exception as e:
            logger.exception("OpenRouter request failed")
            raise HTTPException(
                status_code=502,
                detail=f"OpenRouter request failed: {_openrouter_exception_detail(e)}",
            ) from e
    else:
        if settings.model_provider == "none":
            raise HTTPException(
                status_code=400,
                detail="AI is disabled (MODEL_PROVIDER=none) and no user OpenRouter config is set.",
            )
        provider = get_provider()
        resp = await provider.run(system=system, user=user_prompt)

    raw = resp.text
    data: dict[str, Any] = {}

    # Best-effort JSON extraction: accept either raw JSON or a message containing a JSON object.
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            data = parsed
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                parsed2 = json.loads(m.group(0))
                if isinstance(parsed2, dict):
                    data = parsed2
            except Exception:
                data = {}

    # Filter unknown keys server-side.
    data = {k: v for k, v in data.items() if k in schema}

    return ExtractEntitiesResponse(data=data, raw_text=raw)


@router.post("/generate-template")
async def generate_template(
    req: GenerateTemplateRequest,
    user: Optional[User] = Depends(get_optional_user),
) -> AIResult:
    system = (
        "You are a legal drafting assistant. "
        "Generate a clean plain-text DOCUMENT TEMPLATE in Russian. "
        "IMPORTANT: Do NOT output real personal data values. "
        "Use placeholders in double braces like {{customer.fio}}, {{executor.name}}, {{object.address}}, {{project.price}}. "
        "Prefer using the provided placeholders list and the provided macro placeholders (e.g., {{customer.requisites}}). "
        "If needed, you may introduce new placeholder keys in dot notation. "
        "Return only the template text, no explanations."
    )

    placeholders = (
        "Available placeholders (examples):\n"
        "- Parties: {{customer.requisites}}, {{executor.requisites}}, {{customer.contacts}}, {{executor.contacts}}, "
        "{{customer.fio}}, {{customer.fio.short}}, {{customer.status}}, {{customer.phone}}, {{customer.email}}, "
        "{{executor.name}}, {{executor.phone}}, {{executor.email}}\n"
        "- Object: {{object.summary}}, {{object.address}}, {{object.country}}, {{object.city}}, {{object.house}}, {{object.entrance}}, {{object.apartment}}, {{object.type}}, {{object.area.sqm}}, {{object.rooms.count}}, "
        "{{object.rooms.list}}, {{object.floor.fraction}}, {{object.bathrooms.count}}, {{object.balcony}}, "
        "{{object.residents.count}}, {{object.pets}}, {{object.pets.notes}}\n"
        "- Project: {{project.brief}}, {{project.scope}}, {{project.style}}, {{project.budget}}, {{project.deadline}}, "
        "{{project.price}}, {{project.price.per_sqm}}, {{project.payment.terms}}, {{project.payment.methods}}, "
        "{{project.revisions.included}}, {{project.revisions.extra}}, "
        "{{project.author.supervision}}, {{project.site.visits.count}}, {{project.site.visits.paid_by}}, {{project.site.visits.expenses}}, "
        "{{project.procurement.buys.paid_by}}, {{project.procurement.delivery.acceptance_by}}, "
        "{{project.procurement.lifting.assembly.paid_by}}, {{project.procurement.storage.paid_by}}, "
        "{{project.communication}}, {{project.communication.channel}}, {{project.communication.details}}, {{project.communication.rules}}, "
        "{{project.approval.sla}}, {{project.deadline.shift.terms}}, {{project.penalties.terms}}, "
        "{{project.deliverables}}, {{project.deliverables.inline}}\n"
    )

    user_parts: list[str] = [placeholders]

    if req.entities:
        user_parts.append(
            "Entity values (for choosing variants only; DO NOT copy these values into the output, use placeholders instead):\n"
            + str(req.entities)
        )

    if req.instructions:
        user_parts.append("User request/instructions:\n" + req.instructions)

    if req.base_text:
        user_parts.append("Base text to adapt (optional):\n" + req.base_text)

    user_prompt = "\n\n---\n\n".join(user_parts)

    if user:
        with get_session() as session:
            rt = _get_openrouter_runtime(session, user)
        if rt:
            base_url, api_key, model = rt
            try:
                resp = await run_openai_compatible(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    system=system,
                    user=user_prompt,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"OpenRouter config error: {e}") from e
            except Exception as e:
                logger.exception("OpenRouter request failed")
                raise HTTPException(
                    status_code=502,
                    detail=f"OpenRouter request failed: {_openrouter_exception_detail(e)}",
                ) from e
            return AIResult(text=resp.text)

    if settings.model_provider == "none":
        raise HTTPException(
            status_code=400,
            detail="AI is disabled (MODEL_PROVIDER=none). Configure backend/.env to enable.",
        )

    provider = get_provider()
    resp = await provider.run(system=system, user=user_prompt)
    return AIResult(text=resp.text)


@router.post("/chat")
async def chat(req: ChatRequest, current_user: User = Depends(get_current_user)) -> ChatResponse:
    msgs = req.messages or []
    # Keep it simple and safe: require at least one user message.
    if not any(m.role == "user" and (m.text or "").strip() for m in msgs):
        raise HTTPException(status_code=400, detail="messages must include a user message")

    # Optionally include document context.
    doc_context = ""
    if req.version_id:
        v = _get_version_or_404(req.version_id, user_id=current_user.id)
        doc_context = read_version_text(v)

    system = (
        "You are a helpful assistant for drafting and reviewing Russian legal documents. "
        "Answer in Russian. Be concise and actionable. "
        "If the user asks to generate or modify a document, propose clear steps or a draft."
    )

    parts: list[str] = []
    if doc_context:
        parts.append("Document context:\n" + doc_context)

    # Include recent conversation (cap to avoid huge prompts).
    recent = msgs[-20:]
    convo_lines: list[str] = []
    for m in recent:
        t = (m.text or "").strip()
        if not t:
            continue
        prefix = "User" if m.role == "user" else "Assistant"
        convo_lines.append(f"{prefix}: {t}")
    parts.append("Conversation:\n" + "\n".join(convo_lines))

    user_prompt = "\n\n---\n\n".join(parts)

    with get_session() as session:
        rt = _get_openrouter_runtime(session, current_user)

    if rt:
        base_url, api_key, model = rt
        try:
            resp = await run_openai_compatible(
                base_url=base_url,
                api_key=api_key,
                model=model,
                system=system,
                user=user_prompt,
            )
            return ChatResponse(text=resp.text)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"OpenRouter config error: {e}") from e
        except Exception as e:
            logger.exception("OpenRouter request failed")
            raise HTTPException(
                status_code=502,
                detail=f"OpenRouter request failed: {_openrouter_exception_detail(e)}",
            ) from e

    if settings.model_provider == "none":
        return ChatResponse(
            text=(
                "AI сейчас отключен (MODEL_PROVIDER=none) и для аккаунта не настроен OpenRouter. "
                "Добавьте OpenRouter API key и выберите модель в меню чат-бота, "
                "после чего чат начнет отвечать."
            )
        )

    provider = get_provider()
    resp = await provider.run(system=system, user=user_prompt)
    return ChatResponse(text=resp.text)


@router.post("/summarize")
async def summarize(
    req: SummarizeRequest,
    async_mode: bool = Query(default=False, alias="async"),
    current_user: User = Depends(get_current_user),
) -> AIResult:
    return await _run_ai_action(
        kind="summarize",
        version_id=req.version_id,
        system="You are a legal assistant. Summarize the document succinctly.",
        user_instructions=req.instructions,
        async_mode=async_mode,
        user=current_user,
    )


@router.post("/compare")
async def compare(
    req: CompareRequest,
    async_mode: bool = Query(default=False, alias="async"),
    current_user: User = Depends(get_current_user),
) -> AIResult:
    left = _get_version_or_404(req.left_version_id, user_id=current_user.id)
    right = _get_version_or_404(req.right_version_id, user_id=current_user.id)

    if async_mode:
        task = _create_task(kind="compare", document_id=left.document_id, version_id=left.id)
        enqueue_task(
            {
                "task_id": task.id,
                "kind": "compare",
                "left_version_id": left.id,
                "right_version_id": right.id,
                "instructions": req.instructions,
            }
        )
        return AIResult(text="queued", task_id=task.id)

    system = "You are a legal assistant. Compare two versions of a document and describe changes in a structured way."
    user_prompt = read_version_text(left) + "\n\n---\n\n" + read_version_text(right)
    if req.instructions:
        user_prompt = req.instructions + "\n\n" + user_prompt

    with get_session() as session:
        rt = _get_openrouter_runtime(session, current_user)
    if rt:
        base_url, api_key, model = rt
        try:
            resp = await run_openai_compatible(
                base_url=base_url,
                api_key=api_key,
                model=model,
                system=system,
                user=user_prompt,
            )
            return AIResult(text=resp.text)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"OpenRouter config error: {e}") from e
        except Exception as e:
            logger.exception("OpenRouter request failed")
            raise HTTPException(
                status_code=502,
                detail=f"OpenRouter request failed: {_openrouter_exception_detail(e)}",
            ) from e

    if settings.model_provider == "none":
        raise HTTPException(
            status_code=400,
            detail="AI is disabled (MODEL_PROVIDER=none) and no user OpenRouter config is set.",
        )

    provider = get_provider()
    resp = await provider.run(system=system, user=user_prompt)
    return AIResult(text=resp.text)


@router.post("/translate/bilingual")
async def translate_bilingual(
    req: TranslateBilingualRequest,
    async_mode: bool = Query(default=False, alias="async"),
    current_user: User = Depends(get_current_user),
) -> AIResult:
    system = (
        "You are a professional legal translator. "
        "Return a bilingual two-column representation in plain text as a table-like layout."
    )
    user_prompt = (
        f"Translate from {req.source_lang} to {req.target_lang}. "
        "Keep legal meaning.\n\n"
        + read_version_text(_get_version_or_404(req.version_id, user_id=current_user.id))
    )

    return await _run_ai_action(
        kind="translate_bilingual",
        version_id=req.version_id,
        system=system,
        user_instructions=user_prompt,
        async_mode=async_mode,
        already_built_user=True,
        user=current_user,
    )


async def _run_ai_action(
    *,
    kind: Literal["summarize", "translate_bilingual"],
    version_id: str,
    system: str,
    user_instructions: Optional[str],
    async_mode: bool,
    already_built_user: bool = False,
    user: User,
) -> AIResult:
    current_user = user
    version = _get_version_or_404(version_id, user_id=current_user.id)

    if async_mode:
        task = _create_task(kind=kind, document_id=version.document_id, version_id=version.id)
        enqueue_task(
            {
                "task_id": task.id,
                "kind": kind,
                "version_id": version.id,
                "system": system,
                "instructions": user_instructions,
            }
        )
        return AIResult(text="queued", task_id=task.id)

    if already_built_user:
        user_prompt = user_instructions or ""
    else:
        user_prompt = read_version_text(version)
        if user_instructions:
            user_prompt = user_instructions + "\n\n" + user_prompt

    with get_session() as session:
        rt = _get_openrouter_runtime(session, current_user)
    if rt:
        base_url, api_key, model = rt
        try:
            resp = await run_openai_compatible(
                base_url=base_url,
                api_key=api_key,
                model=model,
                system=system,
                user=user_prompt,
            )
            return AIResult(text=resp.text)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"OpenRouter config error: {e}") from e
        except Exception as e:
            logger.exception("OpenRouter request failed")
            raise HTTPException(
                status_code=502,
                detail=f"OpenRouter request failed: {_openrouter_exception_detail(e)}",
            ) from e

    if settings.model_provider == "none":
        raise HTTPException(
            status_code=400,
            detail="AI is disabled (MODEL_PROVIDER=none) and no user OpenRouter config is set.",
        )

    provider = get_provider()
    resp = await provider.run(system=system, user=user_prompt)
    return AIResult(text=resp.text)


def _create_task(*, kind: str, document_id: str | None, version_id: str | None) -> Task:
    with get_session() as session:
        task = Task(
            kind=kind,
            status=TaskStatus.pending,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            document_id=document_id,
            version_id=version_id,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        return task


def _get_version_or_404(version_id: str, *, user_id: Optional[str] = None) -> DocumentVersion:
    with get_session() as session:
        if user_id:
            v = session.exec(
                select(DocumentVersion)
                .join(Document, Document.id == DocumentVersion.document_id)
                .where(DocumentVersion.id == version_id)
                .where(Document.owner_user_id == user_id)
                .limit(1)
            ).first()
        else:
            v = session.get(DocumentVersion, version_id)

        if not v:
            raise HTTPException(status_code=404, detail="Version not found")
        return v


 
