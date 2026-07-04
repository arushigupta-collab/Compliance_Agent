"""OpenRouter (Claude) narrative + per-stage analysis helper.

Used for document-reading confirmation, the risk narrative, and per-stage
insights/reasoning. Gracefully degrades to deterministic text when
OPENROUTER_API_KEY is unset, so the pipeline runs offline and the oracle stays
reproducible (spec §13: rules where auditability is needed, LLM where judgment helps).
"""
from __future__ import annotations

import json
import re

import httpx

from app.config import settings

_SYSTEM = ("You are a senior compliance analyst at RAK Digital Assets Oasis (RAK DAO). "
           "Be precise, regulatory in tone, and concise. Never invent facts not in the input.")


def available() -> bool:
    return bool(settings.openrouter_api_key)


def _chat(prompt: str, *, max_tokens: int = 500, temperature: float = 0.2) -> str:
    resp = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.openrouter_api_key}",
                 "Content-Type": "application/json"},
        json={"model": settings.openrouter_model,
              "messages": [{"role": "system", "content": _SYSTEM},
                           {"role": "user", "content": prompt}],
              "max_tokens": max_tokens, "temperature": temperature},
        timeout=45.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM response."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(m.group(0)) if m else {}


def narrative(prompt: str, *, fallback: str, max_tokens: int = 300) -> str:
    if not available():
        return fallback
    try:
        return _chat(prompt, max_tokens=max_tokens)
    except Exception:
        return fallback


def stage_analysis(*, stage: str, company_name: str, facts: dict,
                   fallback_reasoning: str, fallback_insights: list[str]) -> dict:
    """Return {reasoning, insights[], source} for a pipeline stage.

    With an OpenRouter key: asks Claude for a short rationale + 3-5 insights,
    grounded strictly in `facts`. Without: returns the deterministic fallback.
    """
    if not available():
        return {"reasoning": fallback_reasoning, "insights": fallback_insights, "source": "rules"}
    prompt = (
        f"Compliance pipeline stage: {stage}.\n"
        f"Company: {company_name}.\n"
        f"Structured facts (JSON):\n{json.dumps(facts, default=str, indent=2)}\n\n"
        "Write an analyst note for this stage. Return ONLY JSON of the form:\n"
        '{"reasoning": "2-3 sentence rationale for the decision", '
        '"insights": ["3 to 5 short, specific insights or watch-items"]}\n'
        "Ground every statement in the facts above; do not fabricate."
    )
    try:
        data = _extract_json(_chat(prompt))
        reasoning = str(data.get("reasoning") or "").strip() or fallback_reasoning
        insights = [str(x).strip() for x in (data.get("insights") or []) if str(x).strip()]
        return {"reasoning": reasoning, "insights": insights or fallback_insights, "source": "llm"}
    except Exception:
        return {"reasoning": fallback_reasoning, "insights": fallback_insights, "source": "rules"}
