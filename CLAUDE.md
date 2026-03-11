# Контекст проекта

**Сказкотерапевт** — Telegram-бот для генерации персонализированных терапевтических сказок для детей.

Родитель описывает ребёнка в свободной форме. Бот генерирует сказку через Gemini, рисует иллюстрацию через Imagen 3, оформляет всё в Google Doc и возвращает текст + ссылку на PDF.

Интеграция с Telegram реализована через **SmartBot Pro** (не через Telegram Bot API напрямую).

Интеграция со SmartBot описана в docs/smartbot_integration.md

---

# Ключевые файлы и их роль

| Файл | Роль |
|------|------|
| `main.py` | FastAPI-сервер. Единственный эндпоинт: `POST /generate`. Оркестрирует весь пайплайн. |
| `gemini_client.py` | Два вызова Gemini: `generate_story(question)` и `generate_image_prompt(story)`. Модель: `gemini-3-pro-preview`, регион `global`. |
| `image_generator.py` | Генерация PNG через Imagen 3 (`imagen-3.0-generate-001`). Возвращает байты. |
| `google_docs_client.py` | Копирует шаблон Google Doc, заменяет `{{STORY}}` и `{{IMAGE}}`, публикует, возвращает PDF-ссылку. |
| `smartbot_client.py` | POST на `https://api.smartbotpro.ru/blocks/execute` с текстом сказки в поле `data.Messagetext`. |
| `prompts.py` | Два промта: `GENERATE_STORY_PROMPT` (полный, написан владельцем) и `GENERATE_IMAGE_PROMPT_PROMPT` (заглушка). |

---

# Что уже сделано

- [x] FastAPI-сервер с эндпоинтом `POST /generate`
- [x] Интеграция с Vertex AI Gemini (генерация сказки)
- [x] Интеграция с Imagen 3 (генерация иллюстрации)
- [x] Создание Google Doc из шаблона с вставкой текста и картинки
- [x] Отправка ответа через SmartBot Pro
- [x] Промт для генерации сказки написан владельцем и вставлен в `prompts.py`
- [x] `.env.example` со всеми нужными переменными
- [x] `requirements.txt`

---

---

# Важные решения

- **Парсинг + генерация сказки — один запрос к Gemini.** Промт сам извлекает данные о ребёнке и сразу генерирует сказку. Отдельного шага парсинга нет.
- **Аутентификация GCP** — через Application Default Credentials локально, через service account JSON на VPS.
- **Формат ответа SmartBot**: поле называется `Messagetext` (с заглавной буквы), находится внутри `data`.

---

# Переменные окружения

```
SMARTBOT_ACCESS_TOKEN      — токен SmartBot Pro
SMARTBOT_CHANNEL_ID        — ID канала SmartBot Pro
SMARTBOT_BLOCK_ID          — ID блока для отправки ответа
GOOGLE_CLOUD_PROJECT       — project-5c6fc698-9b69-4d2d-95d
```
