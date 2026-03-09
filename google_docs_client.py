import io
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

TEMPLATE_ID = os.getenv("GOOGLE_DOCS_TEMPLATE_ID")

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]


def _get_credentials():
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "google-credentials.json")
    if os.path.exists(credentials_path):
        return service_account.Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    else:
        import google.auth
        credentials, _ = google.auth.default(scopes=SCOPES)
        return credentials


def create_doc_from_template(story: str, image_bytes: bytes, title: str) -> str:
    """
    Копирует шаблонный Google Doc, вставляет текст сказки и картинку.
    Возвращает публичную ссылку на документ.
    """
    creds = _get_credentials()
    drive_service = build("drive", "v3", credentials=creds)
    docs_service = build("docs", "v1", credentials=creds)

    # 1. Копируем шаблон в указанную папку
    copy_response = drive_service.files().copy(
        fileId=TEMPLATE_ID,
        body={"name": title, "parents": ["1Py3vE4rQG71HV9QLgwe7pPEhWvDepVoh"]},
    ).execute()
    doc_id = copy_response["id"]

    # 2. Загружаем картинку на Drive в указанную папку
    image_media = MediaIoBaseUpload(io.BytesIO(image_bytes), mimetype="image/png")
    image_file = drive_service.files().create(
        body={"name": f"{title}_image.png", "parents": ["1Py3vE4rQG71HV9QLgwe7pPEhWvDepVoh"]},
        media_body=image_media,
        fields="id, webContentLink",
    ).execute()
    image_file_id = image_file["id"]

    # Делаем картинку публично доступной (нужно для вставки в Docs)
    drive_service.permissions().create(
        fileId=image_file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()
    image_url = f"https://drive.google.com/uc?id={image_file_id}"

    # 3. Получаем структуру документа, чтобы найти плейсхолдеры
    doc = docs_service.documents().get(documentId=doc_id).execute()
    content = doc.get("body", {}).get("content", [])

    # 4. Собираем батч-запросы на замену плейсхолдеров
    # Шаблон должен содержать {{STORY}} и {{IMAGE}} в тексте.
    requests = [
        {
            "replaceAllText": {
                "containsText": {"text": "{{STORY}}", "matchCase": True},
                "replaceText": story,
            }
        },
    ]

    # Вставляем картинку: находим позицию плейсхолдера {{IMAGE}} и заменяем на InlineImage
    image_index = _find_placeholder_index(content, "{{IMAGE}}")
    if image_index is not None:
        requests += [
            # Сначала удаляем плейсхолдер
            {
                "replaceAllText": {
                    "containsText": {"text": "{{IMAGE}}", "matchCase": True},
                    "replaceText": "",
                }
            },
            # Затем вставляем картинку в найденную позицию
            {
                "insertInlineImage": {
                    "location": {"index": image_index},
                    "uri": image_url,
                    "objectSize": {
                        "height": {"magnitude": 300, "unit": "PT"},
                        "width": {"magnitude": 300, "unit": "PT"},
                    },
                }
            },
        ]

    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests},
    ).execute()

    # 5. Открываем доступ к документу по ссылке
    drive_service.permissions().create(
        fileId=doc_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    return f"https://docs.google.com/document/d/{doc_id}/export?format=pdf"


def _find_placeholder_index(content: list, placeholder: str) -> int | None:
    """Ищет индекс символа плейсхолдера в теле документа."""
    for element in content:
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        for pe in paragraph.get("elements", []):
            text_run = pe.get("textRun")
            if text_run and placeholder in text_run.get("content", ""):
                return pe.get("startIndex")
    return None
