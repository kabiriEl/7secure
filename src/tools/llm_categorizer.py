"""LLM-based cybersecurity categorization via Ollama Cloud.

This module provides strict, prompt-driven classification with no keyword-based
taxonomy scoring.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ollama import Client

from src.configs.config import settings


ALLOWED_CATEGORIES: List[str] = [
    "AI Security & Threats",
    "Threat Intelligence",
    "Malware & Ransomware",
    "Vulnerabilities & Exploits",
    "Cloud & SaaS Security",
    "Identity & Access Management",
    "SOC & Automation",
    "Data Protection & Privacy",
    "Security Culture & Human Factors",
    "Compliance & Regulation",
    "Data Breaches",
]

ALLOWED_PRIORITIES = {"critical", "high", "medium", "low"}


CLASSIFIER_SYSTEM_PROMPT = """ ROLE
You are a senior cybersecurity analyst and editor for the 7secure newsletter.

Your task is to analyze a cybersecurity-related article and classify it based on its dominant theme, intent, and operational impact — not keyword frequency.

Think like an experienced security editor.

 OBJECTIVE
From the provided article (Title + Content), determine:

One Primary Category (mandatory)

Zero to Three Secondary Categories (optional)

Maximum Two Subtopics

Priority Level

Flags (if applicable)

 OVERRIDE RULES (Strict Priority Order)
Apply these rules in order. Higher rules override lower ones.

1- Breach Override
If confirmed exposed, leaked, or stolen data:

"primary_category": "Data Breaches"

"breach": true

2- Zero-Day / Active Exploitation Override
If zero-day vulnerability OR active exploitation:

"primary_category": "Vulnerabilities & Exploits"

"zero_day": true

Priority = "critical"

3- Regulatory Update Rule
If the article discusses:

New laws or regulations

Official regulatory updates

Government cybersecurity mandates

Enforcement actions or fines

Mandatory compliance deadlines

Updated regulatory requirements (e.g., NIS2, DORA, CRA, NIST) framed as official developments

Then:

"primary_category": "Compliance & Regulation"

"regulatory_update": true

 Important:
"Regulatory Watch" is NOT a category.
It is a frontend menu triggered when "regulatory_update": true.

 ALLOWED CATEGORIES (PRIMARY & SECONDARY)
Use ONLY these exact values:

AI Security & Threats

Threat Intelligence

Malware & Ransomware

Vulnerabilities & Exploits

Cloud & SaaS Security

Identity & Access Management

SOC & Automation

Data Protection & Privacy

Security Culture & Human Factors

Compliance & Regulation

Data Breaches

 SUBTOPICS RULES
Maximum 2

Must reflect strongest technical or regulatory focus

Do NOT invent new taxonomy items

If none clearly apply, return empty array

 PRIORITY RULES
Assign:

"critical" → zero-day, active exploitation, major breach, regulatory enforcement

"high" → ransomware, severe vulnerabilities, large campaigns

"medium" → framework updates, architectural guidance, vendor security releases

"low" → opinion pieces, awareness content

 CLASSIFICATION PRINCIPLES
Do NOT classify based on keyword frequency.

Identify the dominant theme.

Choose the category with the highest operational impact.

Architecture story → Cloud, IAM, SOC, etc.

Campaign tracking story → Threat Intelligence.

AI attack surface → AI Security & Threats.

Governance/compliance discussion → Compliance & Regulation.

Regulatory enforcement/deadline → Compliance & Regulation + regulatory_update=true.

OUTPUT FORMAT (JSON ONLY):
{
  "primary_category": "one allowed category",
  "secondary_categories": ["0-3 allowed categories, unique, excluding primary"],
  "subtopics": ["0-2 short subtopics"],
  "priority": "critical|high|medium|low",
  "flags": {
    "breach": true|false,
    "zero_day": true|false,
    "regulatory_update": true|false
  }
}

Return ONLY valid JSON. No extra text."""


def _ollama_client() -> Client:
    if not settings.OLLAMA_API_KEY:
        raise RuntimeError("OLLAMA_API_KEY manquant (Ollama Cloud requis)")
    return Client(
        host="https://ollama.com",
        headers={"Authorization": "Bearer " + settings.OLLAMA_API_KEY},
    )


def _extract_json(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Empty model response")
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")
    payload = raw[start:end + 1]
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Model response JSON must be an object")
    return data


def _validate_result(data: Dict[str, Any]) -> Dict[str, Any]:
    primary = data.get("primary_category")
    if primary not in ALLOWED_CATEGORIES:
        raise ValueError("Invalid primary_category")

    secondary = data.get("secondary_categories", [])
    if not isinstance(secondary, list):
        raise ValueError("secondary_categories must be a list")
    secondary = [s for s in secondary if isinstance(s, str)]
    secondary = [s for s in secondary if s in ALLOWED_CATEGORIES and s != primary]
    dedup_secondary: List[str] = []
    for item in secondary:
        if item not in dedup_secondary:
            dedup_secondary.append(item)
    secondary = dedup_secondary[:3]

    subtopics = data.get("subtopics", [])
    if not isinstance(subtopics, list):
        raise ValueError("subtopics must be a list")
    subtopics = [str(s).strip() for s in subtopics if str(s).strip()][:2]

    priority = str(data.get("priority") or "").strip().lower()
    if priority not in ALLOWED_PRIORITIES:
        raise ValueError("Invalid priority")

    flags_raw = data.get("flags", {})
    if not isinstance(flags_raw, dict):
        flags_raw = {}

    flags = {
        "breach": bool(flags_raw.get("breach", False)),
        "zero_day": bool(flags_raw.get("zero_day", False)),
        "regulatory_update": bool(flags_raw.get("regulatory_update", False)),
    }

    return {
        "primary_category": primary,
        "secondary_categories": secondary,
        "subtopics": subtopics,
        "priority": priority,
        "flags": flags,
    }


def classify_article_with_llm(
    title: str,
    content: str,
    client: Optional[Client] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Classify one article using Ollama Cloud and strict JSON output."""
    llm_client = client or _ollama_client()
    llm_model = model or settings.OLLAMA_MODEL

    user_prompt = f"""ARTICLE TITLE:
{(title or '').strip()}

ARTICLE CONTENT:
{(content or '').strip()[:12000]}

Return ONLY the JSON object."""

    response = llm_client.chat(
        model=llm_model,
        messages=[
            {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        stream=False,
        options={"temperature": 0},
    )

    content_text = (response.get("message", {}) or {}).get("content", "")

    try:
        parsed = _extract_json(content_text)
        return _validate_result(parsed)
    except Exception:
        repair_prompt = f"""Your previous answer was invalid.
Return ONLY a valid JSON object matching the exact schema and category constraints.

Previous answer:
{content_text}
"""
        repaired = llm_client.chat(
            model=llm_model,
            messages=[
                {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": repair_prompt},
            ],
            stream=False,
            options={"temperature": 0},
        )
        repaired_text = (repaired.get("message", {}) or {}).get("content", "")
        parsed = _extract_json(repaired_text)
        return _validate_result(parsed)
