import re
import time
import httpx
import google.auth
import google.auth.transport.requests
from typing import Tuple, Optional

# Small helper to call Vertex's generate endpoint with a plain prompt and return text
async def _call_vertex_generation(
    client: httpx.AsyncClient,
    model_url: str,
    prompt: str,
    timeout: int = 60,
    temperature: float = 0.0,
    max_output_tokens: int = 64,
) -> str:
    # get default credentials and refresh
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)
    token = credentials.token

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "contents": {"role": "USER", "parts": [{"text": prompt}]},
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_output_tokens},
    }

    resp = await client.post(model_url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    # robust path to generated text used elsewhere in this repo
    text = ""
    try:
        text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    except Exception:
        text = data.get("candidates", [{}])[0].get("output", "") or ""
    if not text and isinstance(data, dict):
        # fallback: try join parts if present
        parts = []
        for c in data.get("candidates", []):
            for cont in (c.get("content") or {}).get("parts", []):
                parts.append(cont.get("text", ""))
        text = "\n".join(p for p in parts if p)
    return (text or "").strip()

# parse first integer or float percent from text
def _parse_percent(text: str) -> Optional[float]:
    if not text:
        return None
    # look for number like 87 or 87.5 or "87%"
    m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%?", text)
    if not m:
        return None
    try:
        val = float(m.group(1))
        if val < 0:
            val = 0.0
        if val > 100:
            val = min(val, 100.0)
        return val
    except Exception:
        return None

async def evaluate_via_vertex(
    client: httpx.AsyncClient,
    model_url: str,
    article: str,
    english_summary: str,
    back_translated_summary: Optional[str] = None,
    *,
    source_lang_code: Optional[str] = None,
    source_lang_name: Optional[str] = None,
    target_lang_name: Optional[str] = None,
    timeout: int = 60,
) -> dict:
    """
    Returns:
      {
        "summary_similarity_pct": float,
        "translation_consistency_pct": float,
        "eval_time_seconds": float,   # internal evaluator call time
        "response_time_seconds": float, # same as eval_time_seconds (kept for compatibility)
        "source_language": "hi",
        "source_language_name": "Hindi",
        "target_language": "Hindi",
        "_raw_summary_eval": "...",
        "_raw_trans_eval": "..."
      }
    """
    start = time.perf_counter()
    summary_score = None
    trans_score = None
    gen_text = ""
    gen_text2 = ""

    # Prompt for summary similarity
    prompt_sim = (
        "You are an impartial evaluator. Compare the ARTICLE and the SUMMARY below.\n\n"
        "TASK: On a scale from 0 to 100, rate how well the SUMMARY preserves the ARTICLE's key facts, "
        "names, numbers, dates, locations, and the correct chronological sequence of events. Do NOT add "
        "any new facts or interpretations. OUTPUT: ONLY a single numeric percentage.\n\n"
        "ARTICLE:\n" + article + "\n\nSUMMARY:\n" + english_summary + "\n\nScore:"
    )

    try:
        gen_text = await _call_vertex_generation(client, model_url, prompt_sim, timeout=timeout, temperature=0.0, max_output_tokens=24)
        summary_score = _parse_percent(gen_text)
    except Exception:
        summary_score = None

    if back_translated_summary:
        prompt_trans = (
            "You are an impartial evaluator. Compare the ORIGINAL ENGLISH SUMMARY and the BACK-TRANSLATED TEXT below.\n\n"
            "TASK: On a scale from 0 to 100, rate how accurately the BACK-TRANSLATED TEXT preserves the "
            "meaning, facts, and order of the ORIGINAL ENGLISH SUMMARY. OUTPUT: ONLY a single numeric percentage.\n\n"
            "ORIGINAL ENGLISH SUMMARY:\n" + english_summary + "\n\nBACK-TRANSLATED TEXT:\n" + back_translated_summary + "\n\nScore:"
        )
        try:
            gen_text2 = await _call_vertex_generation(client, model_url, prompt_trans, timeout=timeout, temperature=0.0, max_output_tokens=24)
            trans_score = _parse_percent(gen_text2)
        except Exception:
            trans_score = None

    elapsed = time.perf_counter() - start

    return {
        "summary_similarity_pct": round(summary_score if summary_score is not None else 0.0, 2),
        "translation_consistency_pct": round(trans_score if trans_score is not None else 0.0, 2),
        "eval_time_seconds": round(elapsed, 3),
        "response_time_seconds": round(elapsed, 3),
        "source_language": source_lang_code or "",
        "source_language_name": source_lang_name or "",
        "target_language": target_lang_name or "",
        "_raw_summary_eval": gen_text,
        "_raw_trans_eval": gen_text2
    }