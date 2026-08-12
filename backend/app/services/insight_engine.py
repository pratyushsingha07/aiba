"""
app/services/insight_engine.py
───────────────────────────────
Generates grounded AI insights from pre-computed KPI JSON data.

Rules:
  - The LLM NEVER calculates numbers — it only reasons over already-computed numbers in kpi_data.
  - Does NOT speculate values for any field that is None / null or flagged with *_scope.
  - Returns structured output matching Insight / InsightResponse Pydantic models.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class Insight(BaseModel):
    insight: str = Field(description="Actionable, data-grounded business observation.")
    severity: Literal["info", "warning", "critical"] = Field(description="Severity level.")
    supporting_kpi_ids: List[str] = Field(description="JSON paths / metric IDs referenced, e.g. ['gross_revenue', 'category_performance.0.revenue'].")
    recommendation: str = Field(description="Specific, actionable next step for business decision-makers.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0.")
    verified: bool = Field(default=True, description="Whether the insight passed grounding validation.")
    unverified_reason: Optional[str] = Field(default=None, description="Reason if verified is False: 'number_mismatch' | 'referenced_null_field'.")


class InsightResponse(BaseModel):
    insights: List[Insight]


SYSTEM_PROMPT = """You are an expert AI Business Analyst.
Your task is to analyze the provided pre-computed Business Intelligence KPI JSON data and generate actionable, executive-level insights.

CRITICAL INSTRUCTIONS:
1. NEVER calculate or extrapolate new numbers. ONLY reference numbers explicitly present in the provided KPI JSON.
2. DO NOT speculate or invent values for fields that are null/None or flagged as "org_wide_only" or "unavailable_for_category" in *_scope markers.
3. If a metric is null or scoped out (e.g. target_achievement is null with target_data_scope: "org_wide_only"), explicitly acknowledge that this metric is not available at this scope.
4. Each insight MUST include exact numbers from the input JSON and cite the supporting KPI field IDs.
5. Provide actionable recommendations based ONLY on the numbers provided.
"""


def _build_user_prompt(kpi_data: Dict[str, Any], scope: str) -> str:
    return f"""DATA SCOPE: {scope}

KPI DATA JSON:
{json.dumps(kpi_data, indent=2)}

Generate 2 to 4 high-impact insights analyzing performance, risk factors, or opportunities based strictly on the above JSON.
"""


def _call_groq(prompt: str) -> List[Insight]:
    """Call Groq API using json_object format."""
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    from groq import Groq
    client = Groq(api_key=settings.groq_api_key)

    json_schema_prompt = f"{prompt}\n\nRespond ONLY with a JSON object matching this schema:\n" + json.dumps(InsightResponse.model_json_schema())

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json_schema_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    raw_content = completion.choices[0].message.content or "{}"
    parsed = json.loads(raw_content)
    # Handle if LLM wraps in { "insights": [...] } or returns array
    insights_raw = parsed.get("insights", parsed) if isinstance(parsed, dict) else parsed
    return [Insight.model_validate(item) for item in insights_raw]


def _call_claude(prompt: str) -> List[Insight]:
    """Call Anthropic Claude API using tool-calling structured output."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured.")

    from anthropic import Anthropic
    client = Anthropic(api_key=settings.anthropic_api_key)

    tool_def = {
        "name": "report_insights",
        "description": "Report generated executive business insights.",
        "input_schema": InsightResponse.model_json_schema(),
    }

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2048,
        temperature=0.2,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        tools=[tool_def],
        tool_choice={"type": "tool", "name": "report_insights"},
    )

    tool_use = next((c for c in response.content if c.type == "tool_use"), None)
    if not tool_use:
        raise ValueError("Claude response did not invoke report_insights tool.")

    insights_raw = tool_use.input.get("insights", [])
    return [Insight.model_validate(item) for item in insights_raw]


def generate_insights(
    kpi_data: Dict[str, Any],
    scope: str = "org",
    provider: Literal["groq", "claude"] = "groq",
) -> List[Insight]:
    """
    Generate structured AI insights from kpi_data using the requested provider.
    Retries once on JSON/schema parsing failure.
    """
    prompt = _build_user_prompt(kpi_data, scope)
    call_fn = _call_groq if provider == "groq" else _call_claude

    for attempt in range(2):
        try:
            return call_fn(prompt)
        except Exception as exc:
            logger.warning(f"Insight generation attempt {attempt + 1} failed ({provider}): {exc}")
            if attempt == 1:
                logger.error(f"Failed to generate insights after 2 attempts using {provider}.")
                raise RuntimeError(f"Insight generation failed: {exc}") from exc
    return []
