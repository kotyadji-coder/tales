import logging
import os
import re
import time

from google import genai
from google.genai import types

from prompts import GENERATE_IMAGE_PROMPT_PROMPT, GENERATE_STORY_PROMPT

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = (
    "Ты — профессиональный детский психолог и сертифицированный сказкотерапевт. "
    "Ты работаешь в рамках терапевтической практики. Родители обращаются к тебе за помощью, "
    "описывая проблемы своих детей (страхи, агрессия, тревожность, буллинг, травмы и т.д.). "
    "Твоя задача — создать БЕЗОПАСНУЮ терапевтическую сказку, которая поможет ребёнку. "
    "Описание проблемы родителем — это медицинский/психологический контекст, а не опасный контент. "
    "Ты ВСЕГДА создаёшь добрые, исцеляющие сказки без насилия, жестокости и страшных образов."
)

SANITIZE_PROMPT = (
    "Ты — детский психолог. Родитель описал проблему ребёнка. "
    "Перефразируй запрос родителя в мягкой, терапевтической форме, убрав любые резкие "
    "или потенциально триггерные формулировки. Сохрани ВСЮ важную информацию: "
    "имя, возраст, пол ребёнка, суть проблемы, увлечения, особенности. "
    "Просто опиши ситуацию мягким профессиональным языком.\n\n"
    "Сообщение родителя:\n{question}\n\n"
    "Перефразированный запрос:"
)

_last_backend = "unknown"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
VERTEX_REGION = "global"

FALLBACK_CHAIN = [
    ("ai_studio", "gemini-2.5-pro"),
    ("ai_studio", "gemini-2.5-flash"),
    ("vertex", "gemini-2.5-pro"),
]

SAFETY_SETTINGS = [
    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_MEDIUM_AND_ABOVE"),
    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_LOW_AND_ABOVE"),
    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
]


def _get_ai_studio_client() -> genai.Client:
    return genai.Client(api_key=GEMINI_API_KEY)


def _get_vertex_client() -> genai.Client:
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if credentials_path:
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return genai.Client(vertexai=True, project=PROJECT_ID, location=VERTEX_REGION, credentials=credentials)
    return genai.Client(vertexai=True, project=PROJECT_ID, location=VERTEX_REGION)


def _call_with_fallback(contents, config=None):
    """Try AI Studio gemini-2.5-pro -> AI Studio gemini-2.5-flash -> Vertex gemini-2.5-pro."""
    last_error = None
    for backend, model_name in FALLBACK_CHAIN:
        try:
            if backend == "ai_studio":
                if not GEMINI_API_KEY:
                    logger.info(f"Skipping AI Studio ({model_name}): no API key")
                    continue
                client = _get_ai_studio_client()
            else:
                client = _get_vertex_client()

            tag = f"{backend}/{model_name}"
            for attempt in range(4):
                try:
                    logger.info(f"Calling {tag} (attempt {attempt + 1})")
                    response = client.models.generate_content(
                        model=model_name, contents=contents, config=config,
                    )
                    logger.info(f"Success from {tag}")
                    global _last_backend
                    _last_backend = tag
                    return response
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str.upper():
                        if attempt < 3:
                            wait = 2 ** attempt * 5
                            logger.warning(f"{tag} rate limit, retry {attempt + 1}/3 after {wait}s")
                            time.sleep(wait)
                            continue
                        logger.warning(f"{tag} rate limit exhausted, moving to next backend")
                        last_error = e
                        break
                    else:
                        raise
        except Exception as e:
            logger.warning(f"Failed {backend}/{model_name}: {e}")
            last_error = e
            continue

    raise last_error or RuntimeError("All backends failed")


def get_last_backend() -> str:
    return _last_backend


def _get_finish_reason(response) -> str:
    """Извлекает finish_reason из ответа Gemini."""
    try:
        return str(response.candidates[0].finish_reason)
    except Exception:
        return "unknown"


def _sanitize_question(question: str) -> str:
    """Перефразирует вопрос родителя в мягкой форме через Gemini."""
    logger.info("Sanitizing question to bypass safety filter")
    config = types.GenerateContentConfig(
        safety_settings=SAFETY_SETTINGS,
        system_instruction=SYSTEM_INSTRUCTION,
    )
    response = _call_with_fallback(
        SANITIZE_PROMPT.format(question=question),
        config=config,
    )
    sanitized = (response.text or "").strip()
    if not sanitized:
        raise ValueError("Не удалось перефразировать запрос родителя")
    logger.info(f"Sanitized question: {sanitized[:200]}")
    return sanitized


def generate_story(question: str) -> str:
    """Парсит сообщение родителя и генерирует текст сказки."""
    config = types.GenerateContentConfig(
        safety_settings=SAFETY_SETTINGS,
        system_instruction=SYSTEM_INSTRUCTION,
    )

    # Attempt 1: оригинальный вопрос + system instruction
    response = _call_with_fallback(
        GENERATE_STORY_PROMPT.format(question=question),
        config=config,
    )
    text = (response.text or "").strip()

    if text:
        logger.info(f"Raw Gemini response (first 300 chars): {text[:300]}")
        return text

    # Attempt 2: перефразируем вопрос (убираем триггерные слова)
    logger.warning(f"Safety filter triggered (finish_reason={_get_finish_reason(response)}), sanitizing question")
    sanitized = _sanitize_question(question)
    response = _call_with_fallback(
        GENERATE_STORY_PROMPT.format(question=sanitized),
        config=config,
    )
    text = (response.text or "").strip()

    if text:
        logger.info(f"Sanitized attempt succeeded (first 300 chars): {text[:300]}")
        return text

    raise ValueError(
        f"Gemini заблокировал генерацию даже после перефразировки "
        f"(finish_reason={_get_finish_reason(response)})"
    )


def _normalize_marker(line: str) -> str:
    """Убирает из строки всё кроме букв, чтобы сравнивать маркеры нечётко."""
    return re.sub(r"[^а-яёА-ЯЁa-zA-Z]", "", line).upper()


# Маркеры после нормализации
_MARKER_MAP = {
    "СКАЗКА": "story",
    "РЕКОМЕНДАЦИИ": "recommendations",
    "ВОПРОСЫДЛЯОБСУЖДЕНИЯ": "questions",
}


def parse_response(response: str) -> dict:
    """Разбивает ответ Gemini на части по разделителям."""
    sections = {"story": "", "recommendations": "", "questions": ""}

    current_key = None
    for line in response.splitlines():
        normalized = _normalize_marker(line)
        matched = False
        for marker_text, key in _MARKER_MAP.items():
            if marker_text in normalized:
                current_key = key
                matched = True
                break
        if not matched and current_key is not None:
            sections[current_key] += line + "\n"

    result = {k: v.strip().replace("**", "") for k, v in sections.items()}

    # Fallback: если маркеры не найдены, весь текст — сказка
    if not result["story"]:
        logger.warning("Маркеры не найдены в ответе Gemini, используем весь текст как сказку")
        result["story"] = response.strip().replace("**", "")

    return result


def generate_image_prompt(story: str) -> str:
    """Генерирует промт для Imagen 3 на основе текста сказки."""
    config = types.GenerateContentConfig(
        safety_settings=SAFETY_SETTINGS,
        system_instruction=SYSTEM_INSTRUCTION,
    )
    prompt = GENERATE_IMAGE_PROMPT_PROMPT.format(story=story)
    response = _call_with_fallback(prompt, config=config)
    text = (response.text or "").strip()
    if not text:
        raise ValueError("Gemini вернул пустой image prompt")
    return text
