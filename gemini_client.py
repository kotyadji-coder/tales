import os
import re

import vertexai
from vertexai.generative_models import GenerativeModel, HarmBlockThreshold, HarmCategory, SafetySetting

from prompts import GENERATE_IMAGE_PROMPT_PROMPT, GENERATE_STORY_PROMPT

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
REGION = "global"
MODEL_NAME = "gemini-3.1-pro-preview"

SAFETY_SETTINGS = [
    SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.BLOCK_LOW_AND_ABOVE),
    SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.BLOCK_LOW_AND_ABOVE),
    SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.BLOCK_LOW_AND_ABOVE),
    SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.BLOCK_LOW_AND_ABOVE),
]

# Dangerous keywords → safe replacements for input sanitization
_UNSAFE_SUBSTITUTIONS = {
    r"\bубийств[аоу]?\b": "проблема",
    r"\bубива[её]т\b": "расстраивает",
    r"\bубить\b": "обидеть",
    r"\bсмерть\b": "расставание",
    r"\bумер(ла|ли|л)?\b": "ушёл",
    r"\bпистолет\b": "игрушка",
    r"\bоружи[ея]\b": "предмет",
    r"\bнож\b": "предмет",
    r"\bкровь\b": "слёзы",
    r"\bнасили[ея]\b": "конфликт",
    r"\bизнасилова\w+\b": "обидел",
    r"\bсамоубийств[оа]\b": "грусть",
    r"\bсуицид\b": "грусть",
    r"\bнаркотик\w*\b": "конфета",
    r"\bалкогол[ья]\b": "напиток",
    r"\bвзрыв\w*\b": "событие",
    r"\bтеррор\w*\b": "страх",
    r"\bвойн[аы]\b": "конфликт",
}


def sanitize_input(text: str) -> str:
    """Заменяет опасные ключевые слова на безопасные альтернативы."""
    for pattern, replacement in _UNSAFE_SUBSTITUTIONS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


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
    prompt = GENERATE_STORY_PROMPT.format(question=sanitize_input(question))
    response = model.generate_content(prompt, safety_settings=SAFETY_SETTINGS)
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

    return {k: v.strip().replace("**", "") for k, v in sections.items()}


def generate_image_prompt(story: str) -> str:
    """Генерирует промт для Imagen 3 на основе текста сказки."""
    model = _get_model()
    prompt = GENERATE_IMAGE_PROMPT_PROMPT.format(story=story)
    response = model.generate_content(prompt, safety_settings=SAFETY_SETTINGS)
    return response.text.strip()
