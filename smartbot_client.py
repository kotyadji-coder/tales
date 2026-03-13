import json
import logging
import os

import httpx

SMARTBOT_URL = "https://api.smartbotpro.ru/blocks/execute"
ACCESS_TOKEN = os.getenv("SMARTBOT_ACCESS_TOKEN", "quz7AFVUscatV5e2wy7rwd1ZLp2CB004PSy2Mxh5MeGUgoChu4nwSVRumV3mUwQ7")

# Channel configs: channel_id -> {success block_id, error block_id}
CHANNEL_CONFIGS = {
    "8692187786": {  # Telegram
        "block_success": os.getenv("SMARTBOT_BLOCK_ID", "69ad767327915f22d69f79e2"),
        "block_error": "69ad767327915f22d69f79d7",
    },
    "63358055": {  # VK
        "block_success": "69b42a6d0a0f1d927208db03",
        "block_error": "69b42a6d0a0f1d927208db04",
    },
}
DEFAULT_CHANNEL_ID = os.getenv("SMARTBOT_CHANNEL_ID", "8692187786")

logger = logging.getLogger("tales")


def send_message(peer_id: str, text: str, status: str = "success", channel_id: str | None = None) -> None:
    """Отправляет финальное сообщение пользователю через SmartBot Pro."""
    resolved_channel_id = channel_id or DEFAULT_CHANNEL_ID
    config = CHANNEL_CONFIGS.get(resolved_channel_id, CHANNEL_CONFIGS[DEFAULT_CHANNEL_ID])
    block_id = config["block_error"] if status == "error" else config["block_success"]
    logger.info("SmartBot routing: channel_id=%s status=%s block_id=%s", resolved_channel_id, status, block_id)
    payload = {
        "access_token": ACCESS_TOKEN,
        "v": "0.0.1",
        "channel_id": resolved_channel_id,
        "block_id": block_id,
        "peer_id": peer_id,
        "data": {"Messagetext": text, "status": status},
    }
    logger.info("SmartBot payload: %s", json.dumps(payload, ensure_ascii=False))
    response = httpx.post(SMARTBOT_URL, json=payload, timeout=30)
    logger.info("SmartBot response: status=%s body=%s", response.status_code, response.text)
    response.raise_for_status()
