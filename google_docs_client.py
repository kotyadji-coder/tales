import io
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

FOLDER_ID = "1Py3vE4rQG71HV9QLgwe7pPEhWvDepVoh"

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
    Создает новый Google Doc программно, вставляет текст сказки и картинку.
    Возвращает ссылку на PDF документа.
    """
    creds = _get_credentials()
    drive_service = build("drive", "v3", credentials=creds)
    docs_service = build("docs", "v1", credentials=creds)

    # 1. Загружаем картинку на Drive в папку
    image_media = MediaIoBaseUpload(io.BytesIO(image_bytes), mimetype="image/png")
    image_file = drive_service.files().create(
        body={"name": f"{title}_image.png", "parents": [FOLDER_ID]},
        media_body=image_media,
        fields="id",
    ).execute()
    image_file_id = image_file["id"]

    # Делаем картинку публично доступной (нужно для вставки в Docs)
    drive_service.permissions().create(
        fileId=image_file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()
    image_url = f"https://drive.google.com/uc?id={image_file_id}"

    # 2. Создаём новый Google Doc в папке
    doc_metadata = {"name": title, "parents": [FOLDER_ID], "mimeType": "application/vnd.google-apps.document"}
    doc = drive_service.files().create(body=doc_metadata, fields="id").execute()
    doc_id = doc["id"]

    # 3. Собираем запросы для вставки контента в документ
    requests = []

    # Вставляем заголовок (жирный, по центру, размер 24)
    requests.append({
        "insertText": {
            "text": title + "\n",
            "location": {"index": 1},
        }
    })

    # Форматируем заголовок: жирный, размер 24, по центру
    requests.append({
        "updateTextStyle": {
            "range": {
                "startIndex": 1,
                "endIndex": len(title) + 1,
            },
            "textStyle": {
                "bold": True,
                "fontSize": {"magnitude": 24, "unit": "PT"},
            },
            "fields": "bold,fontSize",
        }
    })

    # Выравниваем заголовок по центру
    requests.append({
        "updateParagraphStyle": {
            "range": {
                "startIndex": 1,
                "endIndex": len(title) + 1,
            },
            "paragraphStyle": {
                "alignment": "CENTER",
            },
            "fields": "alignment",
        }
    })

    # Вставляем пустую строку после заголовка
    requests.append({
        "insertText": {
            "text": "\n",
            "location": {"index": len(title) + 2},
        }
    })

    # Вставляем картинку
    image_insert_index = len(title) + 3
    requests.append({
        "insertInlineImage": {
            "location": {"index": image_insert_index},
            "uri": image_url,
            "objectSize": {
                "height": {"magnitude": 400, "unit": "PT"},
                "width": {"magnitude": 400, "unit": "PT"},
            },
        }
    })

    # Вставляем пустую строку после картинки
    requests.append({
        "insertText": {
            "text": "\n\n",
            "location": {"index": image_insert_index + 1},
        }
    })

    # Вставляем текст сказки
    story_insert_index = image_insert_index + 3
    requests.append({
        "insertText": {
            "text": story,
            "location": {"index": story_insert_index},
        }
    })

    # Форматируем текст сказки: размер 11, интервал
    requests.append({
        "updateTextStyle": {
            "range": {
                "startIndex": story_insert_index,
                "endIndex": story_insert_index + len(story),
            },
            "textStyle": {
                "fontSize": {"magnitude": 11, "unit": "PT"},
            },
            "fields": "fontSize",
        }
    })

    # Применяем интервал между строками для сказки
    requests.append({
        "updateParagraphStyle": {
            "range": {
                "startIndex": story_insert_index,
                "endIndex": story_insert_index + len(story),
            },
            "paragraphStyle": {
                "lineSpacing": 150,
            },
            "fields": "lineSpacing",
        }
    })

    # 4. Выполняем все запросы
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests},
    ).execute()

    # 5. Открываем доступ к документу ПО ССЫЛКЕ (anyone with link can view)
    drive_service.permissions().create(
        fileId=doc_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    # 6. Возвращаем ссылку на PDF
    return f"https://docs.google.com/document/d/{doc_id}/export?format=pdf"
