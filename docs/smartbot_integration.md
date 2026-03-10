# Интеграция со SmartBot

## SmartBot отправляет нам:
POST на наш сервер
{
  "user_id": "%user_id%",
  "question": "%user_request%",
  "channel_id": "%channel_id%"
}

## Мы отправляем обратно:
POST https://api.smartbotpro.ru/blocks/execute
{
  "access_token": "ТОКЕН_ПРОЕКТА",
  "v": "0.0.1",
  "channel_id": "ID_КАНАЛА",
  "block_id": "ID_БЛОКА",
  "peer_id": "user_id из входящего запроса",
  "data": {
    "Messagetext": "Ссылка + текст для пользователя"
  }
}

## В SmartBot получаем через:
{{ %public_api_data%.get('Messagetext', '') }}

## Для нового проекта заменить:
- access_token
- channel_id
- block_id
