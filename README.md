# Сказкотерапевт — Telegram-бот для генерации детских сказок

Бот получает сообщение от родителя через Telegram (SmartBot Pro), генерирует персонализированную терапевтическую сказку с иллюстрацией и отправляет результат обратно вместе со ссылкой на PDF-документ.

---

## Как это работает

1. Родитель пишет боту в Telegram в свободной форме: имя ребёнка, возраст, проблему, интересы.
2. SmartBot Pro отправляет POST-запрос на `/generate`.
3. Сервер генерирует сказку через **Gemini** (один запрос: парсинг + генерация).
4. Gemini создаёт промт для иллюстрации, **Imagen 3** рисует картинку.
5. Текст и картинка вставляются в шаблонный **Google Doc**, документ становится доступен по ссылке.
6. Сервер отправляет родителю сказку + ссылку на PDF через SmartBot Pro.

---

## Технологии

| Слой | Инструмент |
|------|------------|
| API-сервер | Python, FastAPI |
| LLM | Vertex AI — Gemini 3 Pro Preview |
| Генерация изображений | Vertex AI — Imagen 3 |
| Документы | Google Docs API + Google Drive API |
| Интеграция с Telegram | SmartBot Pro |
| Деплой | Render |

---

## Структура проекта

```
tales/
├── main.py                # FastAPI-сервер, эндпоинт POST /generate
├── gemini_client.py       # Запросы к Gemini: генерация сказки и промта для картинки
├── image_generator.py     # Генерация иллюстрации через Imagen 3
├── google_docs_client.py  # Копирование шаблона, вставка текста и картинки, публикация
├── smartbot_client.py     # Отправка ответа в SmartBot Pro
├── prompts.py             # Промты для Gemini
├── requirements.txt
├── .env.example           # Пример переменных окружения
└── README.md
```

---

## Переменные окружения

Скопируй `.env.example` в `.env` и заполни значения:

```env
SMARTBOT_ACCESS_TOKEN=    # Токен доступа SmartBot Pro
SMARTBOT_CHANNEL_ID=      # ID канала SmartBot Pro
SMARTBOT_BLOCK_ID=        # ID блока SmartBot Pro для отправки ответа
GOOGLE_CLOUD_PROJECT=     # ID проекта в Google Cloud
GOOGLE_DOCS_TEMPLATE_ID=  # ID шаблонного Google Doc
```

---

## Локальный запуск

### Требования

- Python 3.11+
- Настроенный Google Cloud проект с включёнными API:
  - Vertex AI API
  - Google Docs API
  - Google Drive API

### Шаги

```bash
# 1. Клонировать репозиторий
git clone <repo-url>
cd tales

# 2. Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Настроить переменные окружения
cp .env.example .env
# Заполни .env своими значениями

# 5. Авторизоваться в Google Cloud
gcloud auth application-default login

# 6. Запустить сервер
uvicorn main:app --reload
```

Сервер будет доступен на `http://localhost:8000`.

Проверить эндпоинт:

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"peer_id": "123456789", "message": "Сыну 5 лет, зовут Миша, боится темноты, обожает динозавров"}'
```

---

## Деплой на Render

### Подготовка

1. Создай аккаунт на [render.com](https://render.com) и подключи репозиторий.
2. В Google Cloud создай service account с ролями:
   - `Vertex AI User`
   - `Google Docs Editor` (или `Editor`)
   - `Service Account Token Creator`
3. Скачай JSON-ключ service account.

### Настройка веб-сервиса на Render

| Параметр | Значение |
|----------|----------|
| Environment | Python |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |

### Environment Variables на Render

Добавь все переменные из `.env.example`, плюс:

```
GOOGLE_APPLICATION_CREDENTIALS_JSON=<содержимое JSON-ключа service account одной строкой>
```

И добавь в начало `main.py` логику для чтения ключа из переменной окружения:

```python
import json, os, tempfile

if creds_json := os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w")
    json.dump(json.loads(creds_json), tmp)
    tmp.close()
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name
```

### Настройка SmartBot Pro

В SmartBot Pro укажи Webhook URL: `https://<your-render-app>.onrender.com/generate`

---

## Шаблон Google Doc

Создай документ в Google Docs с двумя плейсхолдерами в тексте:

- `{{STORY}}` — сюда вставляется текст сказки
- `{{IMAGE}}` — сюда вставляется иллюстрация

Скопируй ID документа из URL (`docs.google.com/document/d/<ID>/edit`) в переменную `GOOGLE_DOCS_TEMPLATE_ID`.
