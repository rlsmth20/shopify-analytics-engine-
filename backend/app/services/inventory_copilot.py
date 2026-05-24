from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.schemas import AiChatMessage, AiChatRelatedLink, InventoryAction


SYSTEM_INSTRUCTIONS = """
You are Ask Skubase, a read-only inventory copilot for Shopify merchants.
Answer only inventory, replenishment, dead-stock, supplier, bundle, forecasting,
and Skubase workflow questions. Ground every answer in the supplied shop context.
If the context is missing, say what data is missing. Do not invent SKU metrics,
do not claim Shopify was updated, and do not provide legal, tax, medical, or
financial advice. Keep answers concise, practical, and action-oriented.
"""


@dataclass(frozen=True)
class InventoryChatContext:
    shopify_domain: str
    data_source: str
    actions: list[InventoryAction]

    @property
    def summary(self) -> str:
        urgent = sum(1 for action in self.actions if action.status == "urgent")
        optimize = sum(1 for action in self.actions if action.status == "optimize")
        dead = sum(1 for action in self.actions if action.status == "dead")
        return (
            f"{len(self.actions)} ranked actions "
            f"({urgent} urgent, {optimize} optimize, {dead} dead)"
        )


def answer_inventory_question(
    *,
    messages: list[AiChatMessage],
    context: InventoryChatContext,
) -> tuple[str, str, list[AiChatRelatedLink]]:
    question = _latest_user_message(messages)
    links = _build_related_links(question, context.actions)

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _build_local_answer(question, context), "local", links

    try:
        answer = _call_openai_responses_api(
            api_key=api_key,
            messages=messages,
            context=context,
        )
    except RuntimeError:
        return _build_local_answer(question, context), "local", links

    return answer, "ai", links


def _latest_user_message(messages: list[AiChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message.content.strip()
    return messages[-1].content.strip()


def _call_openai_responses_api(
    *,
    api_key: str,
    messages: list[AiChatMessage],
    context: InventoryChatContext,
) -> str:
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        "instructions": SYSTEM_INSTRUCTIONS.strip(),
        "input": _build_model_input(messages, context),
        "max_output_tokens": 550,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        raise RuntimeError("OpenAI response failed.") from exc

    answer = body.get("output_text")
    if isinstance(answer, str) and answer.strip():
        return answer.strip()

    extracted = _extract_response_text(body)
    if extracted:
        return extracted

    raise RuntimeError("OpenAI response did not include text.")


def _build_model_input(
    messages: list[AiChatMessage],
    context: InventoryChatContext,
) -> str:
    transcript = "\n".join(
        f"{message.role}: {message.content.strip()}"
        for message in messages[-8:]
    )
    return (
        f"Shop: {context.shopify_domain}\n"
        f"Data source: {context.data_source}\n"
        f"Context summary: {context.summary}\n\n"
        "Top inventory actions:\n"
        f"{_format_actions_for_prompt(context.actions[:25])}\n\n"
        "Conversation:\n"
        f"{transcript}"
    )


def _format_actions_for_prompt(actions: list[InventoryAction]) -> str:
    if not actions:
        return "No ranked SKU actions are available yet."

    lines: list[str] = []
    for index, action in enumerate(actions, start=1):
        details = [
            f"{index}. {action.name}",
            f"sku={action.sku_id}",
            f"status={action.status}",
            f"priority={action.priority_score:.0f}",
            f"on_hand={action.current_on_hand}",
            f"velocity={action.daily_velocity:.2f}/day",
            f"days_inventory={action.days_of_inventory:.1f}",
            f"lead_time={action.lead_time_days_used}d",
            f"reorder_point={action.reorder_point_units}",
            f"target_units={action.target_inventory_units}",
            f"action={action.recommended_action}",
        ]
        if action.status == "urgent":
            details.append(f"days_until_stockout={action.days_until_stockout:.1f}")
            details.append(f"profit_at_risk=${action.estimated_profit_impact:,.0f}")
        else:
            details.append(f"cash_tied_up=${action.cash_tied_up:,.0f}")
            details.append(f"excess_units={action.excess_units}")
        if action.explanation:
            details.append(f"why={action.explanation}")
        lines.append(" | ".join(details))
    return "\n".join(lines)


def _extract_response_text(body: dict) -> str:
    chunks: list[str] = []
    for item in body.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunk.strip() for chunk in chunks if chunk.strip()).strip()


def _build_local_answer(question: str, context: InventoryChatContext) -> str:
    actions = context.actions
    if not actions:
        return (
            "I do not see ranked SKU actions yet. Connect or sync Shopify, then "
            "Skubase can answer reorder, stockout, dead-stock, and supplier-risk "
            "questions from your catalog data."
        )

    lower_question = question.lower()
    urgent = [action for action in actions if action.status == "urgent"]
    dead_or_optimize = [
        action for action in actions if action.status in {"dead", "optimize"}
    ]

    if any(term in lower_question for term in ("dead", "slow", "cash", "overstock", "stale")):
        candidates = dead_or_optimize[:5]
        if not candidates:
            return "I do not see dead-stock or overstock actions in the current queue."
        return _format_ranked_answer(
            "The biggest cash-recovery opportunities I see are:",
            candidates,
        )

    if any(term in lower_question for term in ("supplier", "vendor", "lead time", "late")):
        long_lead = sorted(
            actions,
            key=lambda action: (action.lead_time_days_used, action.priority_score),
            reverse=True,
        )[:5]
        return _format_ranked_answer(
            "These items deserve a lead-time or supplier review first:",
            long_lead,
        )

    if any(term in lower_question for term in ("reorder", "buy", "po", "purchase")):
        candidates = urgent[:5] or actions[:5]
        return _format_ranked_answer(
            "Start with these reorder decisions:",
            candidates,
        )

    if urgent:
        return _format_ranked_answer(
            "Here is what I would look at first based on the current queue:",
            urgent[:5],
        )

    return _format_ranked_answer(
        "Here are the highest-priority inventory actions right now:",
        actions[:5],
    )


def _format_ranked_answer(prefix: str, actions: list[InventoryAction]) -> str:
    lines = [prefix]
    for action in actions:
        reason = action.explanation or action.recommended_action
        lines.append(
            f"- {action.name}: {action.recommended_action} "
            f"(priority {action.priority_score:.0f}, on hand {action.current_on_hand}, "
            f"{action.days_of_inventory:.1f} days of inventory). {reason}"
        )
    lines.append(
        "Use this as a triage list; review vendor constraints and actual open POs before placing orders."
    )
    return "\n".join(lines)


def _build_related_links(
    question: str,
    actions: list[InventoryAction],
) -> list[AiChatRelatedLink]:
    lower_question = question.lower()
    links = [AiChatRelatedLink(label="Open action queue", href="/actions")]

    if any(term in lower_question for term in ("forecast", "stockout", "reorder", "buy")):
        links.append(AiChatRelatedLink(label="Open forecast", href="/forecast"))
    if any(term in lower_question for term in ("supplier", "vendor", "lead time")):
        links.append(AiChatRelatedLink(label="Open suppliers", href="/suppliers"))
    if any(term in lower_question for term in ("dead", "slow", "cash", "overstock", "stale", "clear")):
        links.append(AiChatRelatedLink(label="Open liquidation", href="/liquidation"))
    if any(term in lower_question for term in ("bundle", "kit", "component")):
        links.append(AiChatRelatedLink(label="Open bundles", href="/bundles"))

    if not actions:
        links.append(AiChatRelatedLink(label="Sync Shopify", href="/store-sync"))

    return links[:4]
