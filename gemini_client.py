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


def generate_image_prompt(story: str) -> str:
    """Генерирует промт для Imagen 3 на основе текста сказки."""
    model = _get_model()
    prompt = GENERATE_IMAGE_PROMPT_PROMPT.format(story=story)
    response = model.generate_content(prompt)
    return response.text.strip()
