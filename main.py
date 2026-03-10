import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from gemini_client import generate_image_prompt, generate_story, parse_response
from image_generator import generate_image
from smartbot_client import send_message
from tale_generator import save_tale

SERVER_URL = "http://72.56.126.111:8000"
TALES_DIR = Path(__file__).parent / "tales"

logger = logging.getLogger("tales")


class GenerateRequest(BaseModel):
    user_id: str
    question: str
    channel_id: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создаём папку для сказок при запуске
    TALES_DIR.mkdir(exist_ok=True)
    yield


app = FastAPI(lifespan=lifespan)

# Статические файлы (картинки сказок)
app.mount("/tales", StaticFiles(directory=str(TALES_DIR)), name="tales")


def _generate_and_send(user_id: str, question: str) -> None:
    """Вся тяжёлая работа — в отдельном потоке, чтобы не блокировать HTTP-ответ."""
    try:
        # 1. Генерируем сказку (парсинг + генерация в одном запросе)
        raw_response = generate_story(question)
        parsed = parse_response(raw_response)

        # 2. Генерируем промт для картинки и саму картинку
        img_prompt = generate_image_prompt(parsed["story"])
        image_bytes = generate_image(img_prompt)

        # 3. Сохраняем сказку в HTML с картинкой
        tale_id = save_tale(
            image_bytes=image_bytes,
            story_text=parsed["story"],
            server_url=SERVER_URL,
            recommendations=parsed["recommendations"],
            questions=parsed["questions"],
        )

        # 4. Отправляем ссылку + текст через SmartBot
        tale_url = f"{SERVER_URL}/tale/{tale_id}"
        final_text = (
            f"🧸 Ваша сказка готова!\n{tale_url}\n\n"
            f"📖 Рекомендации:\n{parsed['recommendations']}\n\n"
            f"💬 Вопросы для обсуждения:\n{parsed['questions']}"
        )
        send_message(peer_id=user_id, text=final_text)

    except Exception:
        logger.exception("Ошибка при генерации сказки для user_id=%s", user_id)
        send_message(peer_id=user_id, text="Произошла ошибка при создании сказки. Попробуйте ещё раз.")


@app.post("/generate")
async def generate(request: GenerateRequest):
    """Принимает запрос и сразу возвращает 200. Генерация идёт в фоне."""
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _generate_and_send, request.user_id, request.question)
    return {"status": "ok"}


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
