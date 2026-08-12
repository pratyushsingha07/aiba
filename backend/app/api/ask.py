"""
app/api/ask.py
───────────────
POST /ask/{dataset_id}

Auth required. Accepts a free-text business question.
Always uses the Claude provider.
Enforces 20 questions/day rate limit per user via usage_log.
Applies grounding validation before returning answer.
"""
from __future__ import annotations

import json
from typing import Any, Dict
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dashboard import get_dashboard
from app.core.auth import CurrentUser, get_current_user
from app.core.config import get_settings
from app.services.grounding_validator import validate_grounding
from app.services.insight_engine import Insight, SYSTEM_PROMPT

router = APIRouter(tags=["ask"])

MAX_QUESTIONS_PER_DAY = 20


class AskRequest(BaseModel):
    question: str


@router.post("/ask/{dataset_id}", status_code=status.HTTP_200_OK)
def ask_question(
    dataset_id: str,
    body: AskRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Answer a free-text question using Claude over scoped KPI data.
    Enforces rate limit of 20 questions per user per day.
    """
    if not body.question.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question cannot be empty.",
        )

    # ── 1. Rate Limiting Check (20 questions/day) ─────────────────────────
    try:
        from app.db import models as db
        count_today = db.get_user_usage_count_today(user_id=current_user.user_id, action="ask_question")
        if count_today >= MAX_QUESTIONS_PER_DAY:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Daily Q&A rate limit exceeded ({MAX_QUESTIONS_PER_DAY} questions/day). Please try again tomorrow.",
            )
    except HTTPException:
        raise
    except Exception:
        pass  # Ignore DB rate limit check in test/dev mode if DB uninitialized

    # ── 2. Fetch scoped dashboard data ────────────────────────────────────
    dashboard_res = get_dashboard(dataset_id=dataset_id, current_user=current_user)
    kpi_data = dashboard_res.get("kpi_data", {})
    scope = kpi_data.get("scope", "org")

    # ── 3. Call Claude ────────────────────────────────────────────────────
    settings = get_settings()

    prompt = f"""DATA SCOPE: {scope}
USER QUESTION: {body.question}

KPI DATA JSON:
{json.dumps(kpi_data, indent=2)}

Answer the user's question using ONLY numbers explicitly present in the KPI JSON.
If answering the question requires org-wide data or metrics that are null/scoped out (e.g. target_data_scope: "org_wide_only"), state clearly that the requested data is not available for your current scope.
"""

    answer_text = ""
    supporting_kpi_ids = []

    try:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured.")

        from anthropic import Anthropic
        client = Anthropic(api_key=settings.anthropic_api_key)

        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            temperature=0.2,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        answer_text = response.content[0].text if response.content else "No response generated."
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process Q&A: {exc}",
        ) from exc

    # ── 4. Grounding Validation ───────────────────────────────────────────
    dummy_insight = Insight(
        insight=answer_text,
        severity="info",
        supporting_kpi_ids=supporting_kpi_ids,
        recommendation="Review scoped metrics.",
        confidence=0.9,
    )
    validated = validate_grounding(
        insights=[dummy_insight],
        kpi_data=kpi_data,
        org_id=current_user.org_id,
        user_id=current_user.user_id,
        dataset_id=dataset_id,
    )[0]

    # ── 5. Record Usage ───────────────────────────────────────────────────
    try:
        from app.db import models as db
        db.record_usage(user_id=current_user.user_id, action="ask_question")
    except Exception:
        pass

    return {
        "dataset_id": dataset_id,
        "scope": scope,
        "question": body.question,
        "answer": answer_text,
        "verified": validated.verified,
        "unverified_reason": validated.unverified_reason,
    }
