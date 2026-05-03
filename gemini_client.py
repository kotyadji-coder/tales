import logging
import os
import re
import time

from google import genai
from google.genai import types

from prompts import GENERATE_IMAGE_PROMPT_PROMPT, GENERATE_STORY_PROMPT

logger = logging.getLogger(__name__)

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


def generate_story(question: str) -> str:
    """Парсит сообщение родителя и генерирует текст сказки."""
    config = types.GenerateContentConfig(safety_settings=SAFETY_SETTINGS)

    # First attempt
    response = _call_with_fallback(
        GENERATE_STORY_PROMPT.format(question=question),
        config=config,
    )
    text = response.text.strip()

    if not text:
        # Second attempt with an explicit safety instruction
        safe_question = (
            f"{question}\n\n"
            f"[СИСТЕМНОЕ ТРЕБОВАНИЕ]: Предыдущая попытка заблокирована фильтром безопасности. "
            f"Напиши максимально мягкую, терапевтическую и абсолютно безопасную для психики ребенка сказку. "
            f"Категорически избегай любых пугающих, жестоких или мрачных подробностей. "
            f"Сфокусируйся исключительно на исцелении, поддержке, любви и позитивном выходе из ситуации."
        )
        response = _call_with_fallback(
            GENERATE_STORY_PROMPT.format(question=safe_question),
            config=config,
        )
        text = response.text.strip()

    if not text:
        finish_reason = None
        try:
            finish_reason = response.candidates[0].finish_reason
        except Exception:
            pass
        raise ValueError(f"Gemini вернул пустой ответ (finish_reason={finish_reason})")

    return text


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
            if normalized == marker_text:
                current_key = key
                matched = True
                break
        if not matched and current_key is not None:
            sections[current_key] += line + "\n"

    return {k: v.strip().replace("**", "") for k, v in sections.items()}


def generate_image_prompt(story: str) -> str:
    """Генерирует промт для Imagen 3 на основе текста сказки."""
    config = types.GenerateContentConfig(safety_settings=SAFETY_SETTINGS)
    prompt = GENERATE_IMAGE_PROMPT_PROMPT.format(story=story)
    response = _call_with_fallback(prompt, config=config)
    return response.text.strip()
