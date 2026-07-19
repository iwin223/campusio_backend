"""Optional BYOK AI-assisted report card comments.

Only invoked when a school has explicitly configured its own provider API
key via /api/ai-settings. Never called automatically, never billed to us —
the school's own key is used against their own account's usage.
"""
import httpx
import json
import re
from typing import Optional


class AIProviderError(Exception):
    """Raised when the configured provider call fails. Message must never
    contain the raw API key or raw request/response headers."""
    pass


SYSTEM_PROMPT = (
    "You are helping a class teacher write a short, professional report "
    "card comment for a student, in the style of a Ghana Education Service "
    "(GES) terminal report: warm but honest, one to two sentences per "
    "field, no exaggeration, appropriate for a parent to read. Respond "
    "with ONLY a JSON object with exactly two keys: class_teacher_remarks "
    "and head_teacher_remarks. No markdown, no extra text, no code fences."
)


def _build_user_prompt(student_first_name: str, report_data: dict) -> str:
    subjects = report_data.get("subjects") or []
    subject_lines = "\n".join(
        f"- {s.get('subject_name')}: {s.get('total_score')}/100 (Grade {s.get('grade')})"
        for s in subjects
    )
    return (
        f"Student: {student_first_name}\n"
        f"Overall average: {report_data.get('overall_average')}/100 "
        f"(Grade {report_data.get('overall_grade')} - {report_data.get('overall_description')})\n"
        f"Attendance: {report_data.get('attendance_display')}\n"
        f"Subjects:\n{subject_lines}"
    )


def _extract_json(text: str) -> dict:
    """Providers sometimes wrap JSON in markdown code fences despite instructions; strip them."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise AIProviderError(f"AI provider returned unparseable output: {e}")
    if "class_teacher_remarks" not in data or "head_teacher_remarks" not in data:
        raise AIProviderError("AI provider response was missing required fields")
    return {
        "class_teacher_remarks": str(data["class_teacher_remarks"]),
        "head_teacher_remarks": str(data["head_teacher_remarks"]),
    }


async def _call_openai(api_key: str, model: Optional[str], user_prompt: str) -> str:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model or "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
            },
        )
        if response.status_code != 200:
            raise AIProviderError(f"OpenAI request failed with status {response.status_code}")
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def _call_anthropic(api_key: str, model: Optional[str], user_prompt: str) -> str:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model or "claude-3-5-haiku-20241022",
                "max_tokens": 400,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_prompt}],
            },
        )
        if response.status_code != 200:
            raise AIProviderError(f"Anthropic request failed with status {response.status_code}")
        data = response.json()
        return data["content"][0]["text"]


async def _call_gemini(api_key: str, model: Optional[str], user_prompt: str) -> str:
    model_name = model or "gemini-1.5-flash"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent",
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": SYSTEM_PROMPT + "\n\n" + user_prompt}]}],
                "generationConfig": {"temperature": 0.7},
            },
        )
        if response.status_code != 200:
            raise AIProviderError(f"Gemini request failed with status {response.status_code}")
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


async def generate_ai_remarks(
    provider: str, api_key: str, model: Optional[str],
    student_first_name: str, report_data: dict,
) -> dict:
    user_prompt = _build_user_prompt(student_first_name, report_data)
    try:
        if provider == "openai":
            raw_text = await _call_openai(api_key, model, user_prompt)
        elif provider == "anthropic":
            raw_text = await _call_anthropic(api_key, model, user_prompt)
        elif provider == "gemini":
            raw_text = await _call_gemini(api_key, model, user_prompt)
        else:
            raise AIProviderError(f"Unknown AI provider: {provider}")
    except httpx.TimeoutException:
        raise AIProviderError("AI provider request timed out")
    except httpx.HTTPError as e:
        raise AIProviderError(f"AI provider request failed: {type(e).__name__}")
    except (KeyError, IndexError):
        raise AIProviderError("AI provider returned an unexpected response shape")
    return _extract_json(raw_text)
