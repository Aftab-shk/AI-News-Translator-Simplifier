import os
import time
import httpx
from typing import Optional
from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from langdetect import detect, LangDetectException
import google.auth
import google.auth.transport.requests
import evaluator
import evaluator_vertex

# --- Load environment ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")

# Vertex summarization model endpoint
SUMMARIZE_MODEL_URL = (
    f"https://us-central1-aiplatform.googleapis.com/v1/projects/{GOOGLE_PROJECT_ID}"
    f"/locations/us-central1/publishers/google/models/gemini-2.0-flash-001:generateContent"
)

GOOGLE_TRANSLATE_URL = f"https://translation.googleapis.com/language/translate/v2?key={GOOGLE_API_KEY}"
API_TIMEOUT = 90

LANG_CONFIG = {
    "English": "en", "Hindi": "hi", "Gujarati": "gu", "Punjabi": "pa",
    "Bengali": "bn", "Marathi": "mr", "Tamil": "ta", "Telugu": "te",
    "Urdu": "ur", "Kannada": "kn", "Malayalam": "ml", "Odia": "or", "Assamese": "as", "Sanskrit": "sa"
}
CODE_TO_NAME = {v: k for k, v in LANG_CONFIG.items()}

app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple summarization prompt
BASE_PROMPT = (
    "You are an expert news editor. Your task is to produce a concise, factual summary "
    "(3–5 sentences) of the following news article.\n\n"
    
    "A complete summary MUST accurately capture BOTH of the following components:\n\n"

    "=== THE MAIN EVENT (What happened) ===\n"
    "- Identify WHO was involved.\n"
    "- Identify WHAT happened.\n"
    "- Identify WHERE and WHEN it happened.\n"
    "- Present the sequence of events in the correct chronological order.\n"
    "- The chain of actions must be logical and 100% accurate.\n\n"

    "=== THE AFTERMATH / RESOLUTION ===\n"
    "- State the official response (e.g., police, emergency services, government officials).\n"
    "- State the direct consequences (e.g., victims taken to hospital, injuries reported, arrests made, roads closed).\n\n"

    "=== STRICT RULES ===\n"
    "1. Preserve ALL key facts exactly as written (names, numbers, locations, dates, times).\n"
    "2. DO NOT add analysis, interpretation, or any information not present in the article.\n"
    "3. DO NOT infer motives, causes, or relationships not explicitly stated.\n"
    "4. DO NOT change the logical timeline or misrepresent cause-and-effect.\n"
    "5. DO NOT use dramatic or emotional language.\n\n"

    "Write a neutral, factual, 3–5 sentence summary that follows these rules strictly."
)

async def _summarize_with_prompt(client: httpx.AsyncClient, article: str, prompt_intro: str,
                                 temperature: float = 0.0, max_tokens: int = 350) -> str:
    try:
        prompt_text = f"{prompt_intro}\n\nArticle:\n{article}\n\nSummary:"
        payload = {
            "contents": {
                "role": "USER",
                "parts": [{"text": prompt_text}]
            },
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}
        }
        scopes = ['https://www.googleapis.com/auth/cloud-platform']
        credentials, project = google.auth.default(scopes=scopes)
        auth_request = google.auth.transport.requests.Request()
        credentials.refresh(auth_request)
        access_token = credentials.token
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        response = await client.post(SUMMARIZE_MODEL_URL, headers=headers, json=payload, timeout=API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        summary = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return summary.strip()
    except Exception as e:
        print('Error in summarization:', e)
        return ""

async def translate_text_google(client: httpx.AsyncClient, text: str, target_lang_code: str) -> str:
    try:
        payload = {'q': text, 'target': target_lang_code, 'format': 'text'}
        response = await client.post(GOOGLE_TRANSLATE_URL, json=payload, timeout=API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        return data['data']['translations'][0]['translatedText']
    except Exception as e:
        print(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail="Translation failed.")

# DEFINE API ROUTES BEFORE STATIC FILES MOUNT
@app.post("/process")
async def process(
    text: str = Body(...),
    target_lang_name: str = Body(...)
):
    if not GOOGLE_API_KEY or not GOOGLE_PROJECT_ID:
        raise HTTPException(status_code=500, detail="Google API credentials not configured.")
    
    try:
        source_lang_code = detect(text)
    except LangDetectException:
        source_lang_code = "en"

    source_language_name = CODE_TO_NAME.get(source_lang_code, source_lang_code)

    start_ts = time.perf_counter()

    async with httpx.AsyncClient() as client:
        # Translate to English if needed
        if source_lang_code != "en":
            english_text = await translate_text_google(client, text, "en")
        else:
            english_text = text

        # Summarize (English)
        english_summary = await _summarize_with_prompt(client, english_text, BASE_PROMPT)

        # Translate summary to target language if needed
        if target_lang_name == "English":
            final_output = english_summary
            back_translated = english_summary
        else:
            target_lang_code = LANG_CONFIG.get(target_lang_name)
            if target_lang_code:
                final_output = await translate_text_google(client, english_summary, target_lang_code)
                # back-translate for consistency check
                back_translated = await translate_text_google(client, final_output, "en")
            else:
                final_output = english_summary
                back_translated = english_summary

        # --- Prefer Vertex-based evaluator if available ---
        eval_res = {
            "summary_similarity_pct": 0.0,
            "translation_consistency_pct": 0.0,
            "eval_time_seconds": 0.0
        }
        try:
            ev = await evaluator_vertex.evaluate_via_vertex(
                client=client,
                model_url=SUMMARIZE_MODEL_URL,
                article=english_text,
                english_summary=english_summary,
                back_translated_summary=back_translated,
                source_lang_code=source_lang_code,
                source_lang_name=CODE_TO_NAME.get(source_lang_code, source_lang_code),
                target_lang_name=target_lang_name,
                timeout=API_TIMEOUT
            )
            eval_res = ev
        except Exception as e:
            # fallback to local evaluator
            summary_similarity = evaluator.compute_summary_similarity(english_text, english_summary)
            translation_consistency = evaluator.compute_translation_consistency(english_summary, back_translated)
            eval_res = {
                "summary_similarity_pct": round(summary_similarity, 2),
                "translation_consistency_pct": round(translation_consistency, 2),
                "eval_time_seconds": 0.0,
                "response_time_seconds": 0.0,
                "source_language": source_lang_code,
                "source_language_name": CODE_TO_NAME.get(source_lang_code, source_lang_code),
                "target_language": target_lang_name
            }

    elapsed = time.perf_counter() - start_ts

    # ensure evaluation object has timing (and language) before returning
    eval_res.setdefault("response_time_seconds", round(elapsed, 3))
    eval_res.setdefault("source_language", source_lang_code)
    eval_res.setdefault("source_language_name", CODE_TO_NAME.get(source_lang_code, source_lang_code))
    eval_res.setdefault("target_language", target_lang_name)

    return {
        "output": final_output,
        "english_summary": english_summary,
        "source_language": source_lang_code,
        "source_language_name": CODE_TO_NAME.get(source_lang_code, source_lang_code),
        "target_language": target_lang_name,
        "response_time_seconds": round(elapsed, 3),
        "evaluation": eval_res
    }

# MOUNT STATIC FILES LAST (after all API routes)
website_path = os.path.join(os.path.dirname(__file__), "..", "Website")
if os.path.exists(website_path):
    app.mount("/", StaticFiles(directory=website_path, html=True), name="static")