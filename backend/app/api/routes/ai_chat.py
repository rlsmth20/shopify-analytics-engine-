from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import require_active_access
from app.db.models import Shop, User
from app.db.session import get_db_session
from app.schemas import AiChatRequest, AiChatResponse
from app.services.inventory_copilot import (
    InventoryChatContext,
    answer_inventory_question,
)
from app.services.inventory_engine import build_inventory_actions
from app.services.shop_settings import (
    build_default_shop_settings,
    load_effective_shop_settings_map,
)
from app.services.shop_skus import load_skus_for_shop


router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=AiChatResponse)
def chat_with_inventory_copilot(
    payload: AiChatRequest,
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> AiChatResponse:
    skus = load_skus_for_shop(db, user.shop_id)
    settings = load_effective_shop_settings_map(db).get(user.shop_id)
    if settings is None:
        settings = build_default_shop_settings()
    actions = build_inventory_actions(skus, lead_time_config=settings.to_lead_time_config())
    actions = sorted(actions, key=lambda action: action.priority_score, reverse=True)
    shop_domain = (
        db.scalar(select(Shop.shopify_domain).where(Shop.id == user.shop_id))
        or "Current Shopify store"
    )

    context = InventoryChatContext(
        shopify_domain=shop_domain,
        data_source="db",
        actions=actions,
    )
    answer, mode, links = answer_inventory_question(
        messages=payload.messages,
        context=context,
    )

    return AiChatResponse(
        answer=answer,
        mode=mode,
        data_source="db",
        context_summary=context.summary,
        related_links=links,
    )
