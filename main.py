from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from gemini_client import generate_image_prompt, generate_story
from image_generator import generate_image
from smartbot_client import send_message
from tale_generator import save_tale

SERVER_URL = "http://72.56.126.111:8000"
TALES_DIR = Path(__file__).parent / "tales"


class GenerateRequest(BaseModel):
    peer_id: str
    message: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создаём папку для сказок при запуске
    TALES_DIR.mkdir(exist_ok=True)
    yield


app = FastAPI(lifespan=lifespan)

# Статические файлы (картинки сказок)
app.mount("/tales", StaticFiles(directory=str(TALES_DIR)), name="tales")


@app.post("/generate")
async def generate(request: GenerateRequest):
    """Генерирует сказку и сохраняет в HTML."""
    peer_id = request.peer_id

    try:
        # 1. Генерируем сказку (парсинг + генерация в одном запросе)
        story = generate_story(request.message)

        # 2. Генерируем промт для картинки и саму картинку
        img_prompt = generate_image_prompt(story)
        image_bytes = generate_image(img_prompt)

        # 3. Сохраняем сказку в HTML с картинкой
        tale_id = save_tale(
            image_bytes=image_bytes,
            story_text=story,
            server_url=SERVER_URL,
        )

        # 4. Формируем ссылку на сказку
        tale_url = f"{SERVER_URL}/tale/{tale_id}"

        # 5. Отправляем сообщение через SmartBot с ссылкой
        final_text = f"✨ Вот твоя сказка! ✨\n\n{tale_url}"
        send_message(peer_id=peer_id, text=final_text)

        return {"url": tale_url, "tale_id": tale_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tale/{tale_id}", response_class=HTMLResponse)
async def get_tale(tale_id: str):
    """Отдаёт HTML страницу сказки."""
    html_path = TALES_DIR / f"{tale_id}.html"

    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Сказка не найдена")

    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/health")
async def health():
    """Проверка статуса сервера."""
    return {"status": "ok"}
