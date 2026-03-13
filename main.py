import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db_logger
from gemini_client import generate_image_prompt, generate_story, parse_response
from image_generator import generate_image
from smartbot_client import send_message
from tale_generator import save_tale

ADMIN_BOT_TOKEN = "8688139519:AAHjXoWLFXvurj5a60z_wghN50OxgnOoXUM"
ADMIN_CHAT_ID = "856877325"
ADMIN_PASSWORD = "protale2026"

SERVER_URL = "https://protale.ru"
TALES_DIR = Path(__file__).parent / "tales"

logger = logging.getLogger("tales")


def _check_password(password: str):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Forbidden")


def _notify_admin(error_message: str, user_id: str) -> None:
    text = f"❌ Ошибка: {error_message}, user: {user_id}"
    try:
        httpx.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage",
            json={"chat_id": ADMIN_CHAT_ID, "text": text},
            timeout=10,
        )
    except Exception:
        logger.exception("Не удалось отправить уведомление администратору")


class GenerateRequest(BaseModel):
    user_id: str
    question: str
    channel_id: str
    callback_url: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    TALES_DIR.mkdir(exist_ok=True)
    yield


app = FastAPI(lifespan=lifespan)

app.mount("/tales", StaticFiles(directory=str(TALES_DIR)), name="tales")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


def _generate_and_send(user_id: str, question: str, channel_id: str, callback_url: str | None = None) -> None:
    """Вся тяжёлая работа — в отдельном потоке, чтобы не блокировать HTTP-ответ."""
    try:
        # 1. Генерируем сказку
        db_logger.log("INFO", "STORY_START", "Генерация сказки начата", user_id=user_id, channel_id=channel_id)
        raw_response = generate_story(question)
        parsed = parse_response(raw_response)

        # 2. Сохраняем сказку
        db_logger.log("INFO", "IMAGE_START", "Генерация изображения начата", user_id=user_id, channel_id=channel_id)
        img_prompt = generate_image_prompt(parsed["story"])

        try:
            image_bytes = generate_image(img_prompt)
            db_logger.log("INFO", "IMAGE_DONE", "Изображение сгенерировано", user_id=user_id, channel_id=channel_id)
        except Exception as img_err:
            db_logger.log("ERROR", "IMAGE_ERROR", f"Ошибка генерации изображения: {img_err}", user_id=user_id, channel_id=channel_id)
            raise

        tale_id = save_tale(
            image_bytes=image_bytes,
            story_text=parsed["story"],
            server_url=SERVER_URL,
            recommendations=parsed["recommendations"],
            questions=parsed["questions"],
        )
        db_logger.log("INFO", "STORY_DONE", f"Сказка сохранена: {tale_id}", user_id=user_id, channel_id=channel_id)

        # 3. Отправляем через SmartBot
        tale_url = f"{SERVER_URL}/tale/{tale_id}"
        recommendations = "\n\n".join(
            line for line in parsed["recommendations"].splitlines() if line.strip()
        )
        questions = "\n\n".join(
            line for line in parsed["questions"].splitlines() if line.strip()
        )
        final_text = (
            f"🧸 Ваша сказка готова!\n{tale_url}\n\n"
            f"📖 Рекомендации:\n{recommendations}\n\n"
            f"💬 Вопросы для обсуждения:\n{questions}"
        )

        try:
            send_message(peer_id=user_id, text=final_text, status="success", channel_id=channel_id)
            db_logger.log("INFO", "CALLBACK_SENT", f"Ответ отправлен в SmartBot, tale_id={tale_id}", user_id=user_id, channel_id=channel_id)
        except Exception as cb_err:
            db_logger.log("ERROR", "CALLBACK_ERROR", f"Ошибка отправки в SmartBot: {cb_err}", user_id=user_id, channel_id=channel_id)
            raise

    except Exception as e:
        error_message = str(e)
        db_logger.log("ERROR", "ERROR", f"Необработанная ошибка: {error_message}", user_id=user_id, channel_id=channel_id)
        logger.exception("Ошибка при генерации сказки для user_id=%s", user_id)
        send_message(peer_id=user_id, text="Произошла ошибка при создании сказки. Попробуйте ещё раз.", status="error", channel_id=channel_id)
        _notify_admin(error_message=error_message, user_id=user_id)
        if callback_url:
            try:
                httpx.post(
                    callback_url,
                    json={"status": "error", "user_id": user_id, "error_message": error_message},
                    timeout=10,
                )
            except Exception:
                logger.exception("Не удалось отправить callback об ошибке")


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "templates" / "index.html"
    return html_path.read_text(encoding="utf-8")


@app.post("/generate")
async def generate(request: Request):
    """Принимает запрос и сразу возвращает 200. Генерация идёт в фоне."""
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")
    body_str = re.sub(
        r'("question":\s*"[^"]*)',
        lambda m: m.group(0).replace("\n", " "),
        body_str,
    )
    data = json.loads(body_str)
    req = GenerateRequest(**data)
    db_logger.log(
        "INFO",
        "REQUEST",
        f"Запрос получен: {req.question[:50]}",
        user_id=req.user_id,
        channel_id=req.channel_id,
    )
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _generate_and_send, req.user_id, req.question, req.channel_id, req.callback_url)
    return {"status": "ok"}


@app.get("/tale/{tale_id}", response_class=HTMLResponse)
async def get_tale(tale_id: str):
    html_path = TALES_DIR / f"{tale_id}.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Сказка не найдена")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/admin/logs", response_class=HTMLResponse)
async def admin_logs(password: str = Query(...)):
    _check_password(password)
    rows = db_logger.get_recent_logs(100)

    level_colors = {"INFO": "#2ecc71", "ERROR": "#e74c3c", "WARNING": "#f39c12"}

    rows_html = ""
    for r in rows:
        color = level_colors.get(r["level"], "#aaa")
        rows_html += (
            f'<tr>'
            f'<td>{r["timestamp"]}</td>'
            f'<td style="color:{color};font-weight:bold">{r["level"]}</td>'
            f'<td>{r["action"] or ""}</td>'
            f'<td>{r["user_id"] or ""}</td>'
            f'<td>{r["channel_id"] or ""}</td>'
            f'<td style="word-break:break-word">{r["message"]}</td>'
            f'</tr>\n'
        )

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Logs — Protale Admin</title>
  <meta http-equiv="refresh" content="30">
  <style>
    body {{ font-family: monospace; background: #111; color: #eee; padding: 20px; }}
    h1 {{ color: #fff; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    th {{ background: #222; color: #aaa; padding: 8px; text-align: left; }}
    td {{ padding: 6px 8px; border-bottom: 1px solid #222; vertical-align: top; }}
    tr:hover td {{ background: #1a1a1a; }}
    .meta {{ color: #666; font-size: 12px; margin-bottom: 12px; }}
    a {{ color: #aaa; }}
  </style>
</head>
<body>
  <h1>Logs</h1>
  <div class="meta">Последние 100 записей · Обновление каждые 30 сек · <a href="/admin/stats?password={password}">Stats</a></div>
  <table>
    <tr><th>Время</th><th>Уровень</th><th>Действие</th><th>User ID</th><th>Channel ID</th><th>Сообщение</th></tr>
    {rows_html}
  </table>
</body>
</html>"""
    return html


@app.get("/admin/stats", response_class=HTMLResponse)
async def admin_stats(password: str = Query(...)):
    _check_password(password)
    stats = db_logger.get_stats_today()

    last_error_html = "—"
    if stats["last_error"]:
        last_error_html = (
            f'<span style="color:#e74c3c">{stats["last_error"]["message"]}</span>'
            f'<br><small style="color:#666">{stats["last_error"]["timestamp"]}</small>'
        )

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Stats — Protale Admin</title>
  <meta http-equiv="refresh" content="30">
  <style>
    body {{ font-family: monospace; background: #111; color: #eee; padding: 20px; }}
    h1 {{ color: #fff; }}
    .card {{ background: #1a1a1a; border-radius: 8px; padding: 20px; margin: 12px 0; display: inline-block; min-width: 200px; }}
    .card .val {{ font-size: 48px; font-weight: bold; }}
    .green {{ color: #2ecc71; }}
    .red {{ color: #e74c3c; }}
    .meta {{ color: #666; font-size: 12px; margin-bottom: 12px; }}
    a {{ color: #aaa; }}
  </style>
</head>
<body>
  <h1>Stats</h1>
  <div class="meta">Сегодня · Обновление каждые 30 сек · <a href="/admin/logs?password={password}">Logs</a></div>
  <div class="card">
    <div class="green val">{stats["stories_today"]}</div>
    <div>Сказок сегодня</div>
  </div>
  &nbsp;
  <div class="card">
    <div class="red val">{stats["errors_today"]}</div>
    <div>Ошибок сегодня</div>
  </div>
  <br><br>
  <div>
    <b>Последняя ошибка:</b><br>
    {last_error_html}
  </div>
</body>
</html>"""
    return html


@app.get("/favicon.ico")
async def favicon():
    return FileResponse("static/favicon.ico")


@app.get("/health")
async def health():
    return {"status": "ok"}
