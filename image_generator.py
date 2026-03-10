import os

import vertexai
from vertexai.preview.vision_models import ImageGenerationModel

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
REGION = "us-central1"
IMAGEN_MODEL = "imagen-3.0-generate-001"


def generate_image(image_prompt: str) -> bytes:
    """
    Генерирует изображение через Imagen 3 и возвращает байты PNG.
    """
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if credentials_path:
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_file(credentials_path)
        vertexai.init(project=PROJECT_ID, location=REGION, credentials=credentials)
    else:
        vertexai.init(project=PROJECT_ID, location=REGION)
    model = ImageGenerationModel.from_pretrained(IMAGEN_MODEL)
    response = model.generate_images(
        prompt=image_prompt,
        number_of_images=1,
        aspect_ratio="1:1",
        person_generation="allow_all",
    )
    image = response.images[0]
    return image._image_bytes
