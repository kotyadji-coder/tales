import json
import logging
import os

import httpx

SMARTBOT_URL = "https://api.smartbotpro.ru/blocks/execute"
ACCESS_TOKEN = os.getenv("SMARTBOT_ACCESS_TOKEN", "quz7AFVUscatV5e2wy7rwd1ZLp2CB004PSy2Mxh5MeGUgoChu4nwSVRumV3mUwQ7")
CHANNEL_ID = os.getenv("SMARTBOT_CHANNEL_ID", "8692187786")
BLOCK_ID_SUCCESS = os.getenv("SMARTBOT_BLOCK_ID", "69ad767327915f22d69f79e2")
BLOCK_ID_ERROR = "69ad767327915f22d69f79d7"

logger = logging.getLogger("tales")


def send_message(peer_id: str, text: str, status: str = "success") -> None:
    """Отправляет финальное сообщение пользователю через SmartBot Pro."""
    block_id = BLOCK_ID_ERROR if status == "error" else BLOCK_ID_SUCCESS
    logger.info("SmartBot routing: status=%s block_id=%s", status, block_id)
    payload = {
        "access_token": ACCESS_TOKEN,
        "v": "0.0.1",
        "channel_id": CHANNEL_ID,
        "block_id": block_id,
        "peer_id": peer_id,
        "data": {"Messagetext": text, "status": status},
    }
    logger.info("SmartBot payload: %s", json.dumps(payload, ensure_ascii=False))
    response = httpx.post(SMARTBOT_URL, json=payload, timeout=30)
    logger.info("SmartBot response: status=%s body=%s", response.status_code, response.text)
    response.raise_for_status()
