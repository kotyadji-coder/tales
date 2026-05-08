import logging
import os
import time

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_last_backend = "unknown"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
IMAGE_BACKENDS = ["vertex"]  # AI Studio free tier has 0 quota for image generation
IMAGE_MODEL = "gemini-2.5-flash-image"


def _get_client(backend: str) -> genai.Client:
    if backend == "ai_studio":
        if not GEMINI_API_KEY:
            raise ValueError("No GEMINI_API_KEY")
        return genai.Client(api_key=GEMINI_API_KEY)
    # vertex
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if credentials_path:
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return genai.Client(vertexai=True, project=PROJECT_ID, location="us-central1", credentials=credentials)
    return genai.Client(vertexai=True, project=PROJECT_ID, location="us-central1")


def generate_image(image_prompt: str) -> bytes:
    """
    Генерирует изображение через Gemini 2.5 Flash Image и возвращает байты PNG.
    Fallback: AI Studio -> Vertex AI.
    """
    safety_settings = [
        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_LOW_AND_ABOVE"),
        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_LOW_AND_ABOVE"),
        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_LOW_AND_ABOVE"),
        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_LOW_AND_ABOVE"),
    ]

    config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(
            aspect_ratio="1:1"
        ),
        safety_settings=safety_settings,
    )

    last_error = None
    for backend in IMAGE_BACKENDS:
        try:
            client = _get_client(backend)
        except ValueError as e:
            logger.info(f"Skipping image backend {backend}: {e}")
            continue

        tag = f"{backend}/{IMAGE_MODEL}"
        for attempt in range(4):
            try:
                logger.info(f"Image generation: {tag} (attempt {attempt + 1})")
                response = client.models.generate_content(
                    model=IMAGE_MODEL,
                    contents=[image_prompt],
                    config=config,
                )

                for part in response.candidates[0].content.parts:
                    if part.inline_data is not None:
                        logger.info(f"Image generated via {tag}")
                        global _last_backend
                        _last_backend = f"{backend}/{IMAGE_MODEL}"
                        return part.inline_data.data

                raise ValueError("No image data in response")
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
                    logger.warning(f"Failed {tag}: {e}")
                    last_error = e
                    break

    raise last_error or ValueError("All image backends failed")


def get_last_backend() -> str:
    return _last_backend
