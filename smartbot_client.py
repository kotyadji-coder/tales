import os

import httpx

SMARTBOT_URL = "https://api.smartbotpro.ru/blocks/execute"
ACCESS_TOKEN = os.getenv("SMARTBOT_ACCESS_TOKEN", "quz7AFVUscatV5e2wy7rwd1ZLp2CB004PSy2Mxh5MeGUgoChu4nwSVRumV3mUwQ7")
CHANNEL_ID = os.getenv("SMARTBOT_CHANNEL_ID", "8321357428")
BLOCK_ID = os.getenv("SMARTBOT_BLOCK_ID", "69ad767327915f22d69f79e2")


def send_message(peer_id: str, text: str) -> None:
    """Отправляет финальное сообщение пользователю через SmartBot Pro."""
    payload = {
        "access_token": ACCESS_TOKEN,
        "v": "0.0.1",
        "channel_id": CHANNEL_ID,
        "block_id": BLOCK_ID,
        "peer_id": peer_id,
        "data": {"Messagetext": text},
    }
    response = httpx.post(SMARTBOT_URL, json=payload, timeout=30)
    response.raise_for_status()
