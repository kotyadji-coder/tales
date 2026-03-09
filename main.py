from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from gemini_client import generate_image_prompt, generate_story
from google_docs_client import create_doc_from_template
from image_generator import generate_image
from smartbot_client import send_message


class GenerateRequest(BaseModel):
    peer_id: str
    message: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/generate")
async def generate(request: GenerateRequest):
    peer_id = request.peer_id

    try:
        # 1. Генерируем сказку (парсинг + генерация в одном запросе)
        story = generate_story(request.message)

        # 2. Генерируем промт для картинки и саму картинку
        img_prompt = generate_image_prompt(story)
        image_bytes = generate_image(img_prompt)

        # 3. Создаём Google Doc и получаем ссылку
        doc_url = create_doc_from_template(
            story=story,
            image_bytes=image_bytes,
            title="Сказка",
        )

        # 4. Собираем финальный текст и отправляем через SmartBot
        final_text = story + "\n\n📖 Скачать и распечатать: " + doc_url
        send_message(peer_id=peer_id, text=final_text)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "ok"}
