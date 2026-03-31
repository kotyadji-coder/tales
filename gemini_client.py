import os

import vertexai
from vertexai.generative_models import GenerativeModel, HarmBlockThreshold, HarmCategory, SafetySetting

from prompts import GENERATE_IMAGE_PROMPT_PROMPT, GENERATE_STORY_PROMPT

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
REGION = "global"
MODEL_NAME = "gemini-3.1-pro-preview"

SAFETY_SETTINGS = [
    SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
]


def _get_model() -> GenerativeModel:
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if credentials_path:
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_file(credentials_path)
        vertexai.init(project=PROJECT_ID, location=REGION, credentials=credentials)
    else:
        vertexai.init(project=PROJECT_ID, location=REGION)
    return GenerativeModel(MODEL_NAME)


def generate_story(question: str) -> str:
    """Парсит сообщение родителя и генерирует текст сказки."""
    model = _get_model()

    # First attempt
    response = model.generate_content(
        GENERATE_STORY_PROMPT.format(question=question),
        safety_settings=SAFETY_SETTINGS,
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
        response = model.generate_content(
            GENERATE_STORY_PROMPT.format(question=safe_question),
            safety_settings=SAFETY_SETTINGS,
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


def parse_response(response: str) -> dict:
    """Разбивает ответ Gemini на части по разделителям."""
    sections = {"story": "", "recommendations": "", "questions": ""}
    markers = {
        "---СКАЗКА---": "story",
        "---РЕКОМЕНДАЦИИ---": "recommendations",
        "---ВОПРОСЫ ДЛЯ ОБСУЖДЕНИЯ---": "questions",
    }

    current_key = None
    for line in response.splitlines():
        stripped = line.strip()
        if stripped in markers:
            current_key = markers[stripped]
        elif current_key is not None:
            sections[current_key] += line + "\n"

    return {k: v.strip().replace("**", "") for k, v in sections.items()}


def generate_image_prompt(story: str) -> str:
    """Генерирует промт для Imagen 3 на основе текста сказки."""
    model = _get_model()
    prompt = GENERATE_IMAGE_PROMPT_PROMPT.format(story=story)
    response = model.generate_content(prompt, safety_settings=SAFETY_SETTINGS)
    return response.text.strip()
