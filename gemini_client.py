import os

import vertexai
from vertexai.generative_models import GenerativeModel

from prompts import GENERATE_IMAGE_PROMPT_PROMPT, GENERATE_STORY_PROMPT

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
REGION = "global"
MODEL_NAME = "gemini-3-pro-preview"


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
    prompt = GENERATE_STORY_PROMPT.format(question=question)
    response = model.generate_content(prompt)
    return response.text.strip()


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

    return {k: v.strip() for k, v in sections.items()}


def generate_image_prompt(story: str) -> str:
    """Генерирует промт для Imagen 3 на основе текста сказки."""
    model = _get_model()
    prompt = GENERATE_IMAGE_PROMPT_PROMPT.format(story=story)
    response = model.generate_content(prompt)
    return response.text.strip()
