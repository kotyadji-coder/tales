# Деплой на Ubuntu VPS

## 1. Подготовка сервера (выполнить один раз)

```bash
# Обновить пакеты
sudo apt update && sudo apt upgrade -y

# Установить Python и pip
sudo apt install -y python3 python3-pip python3-venv

# Создать директорию для проекта
sudo mkdir -p /opt/tales
sudo chown $USER:$USER /opt/tales
cd /opt/tales
```

## 2. Копирование кода на сервер

### Вариант A: Если у вас есть GitHub репозиторий

```bash
cd /opt/tales
git clone https://github.com/YOUR_USERNAME/tales.git .
```

### Вариант B: Копирование файлов через SCP (если нет git)

На локальной машине выполнить:
```bash
scp -r /Users/anastasiamisenko/Documents/projects/tales/* user@YOUR_VPS_IP:/opt/tales/
```

## 3. Установка зависимостей

```bash
cd /opt/tales

# Создать виртуальное окружение
python3 -m venv venv

# Активировать окружение
source venv/bin/activate

# Установить зависимости
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Настройка переменных окружения

```bash
# Скопировать пример конфига
cp .env.example .env

# Отредактировать .env
nano .env
```

**Заполнить в .env:**
```
GOOGLE_CLOUD_PROJECT=project-5c6fc698-9b69-4d2d-95d
GOOGLE_DOCS_TEMPLATE_ID=<ID твоего документа>
SMARTBOT_ACCESS_TOKEN=<твой токен>
SMARTBOT_CHANNEL_ID=<ID канала>
SMARTBOT_BLOCK_ID=<ID блока>
GOOGLE_APPLICATION_CREDENTIALS=./google-credentials.json
```

## 5. Копирование Google Cloud ключа

На локальной машине:
```bash
scp /Users/anastasiamisenko/Documents/projects/tales/google-credentials.json user@YOUR_VPS_IP:/opt/tales/
```

На сервере проверить:
```bash
ls -la /opt/tales/google-credentials.json
```

## 6. Запуск Uvicorn на порту 8000

### Вариант A: Запуск вручную (для тестирования)

```bash
cd /opt/tales
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Вариант B: Запуск как systemd сервис (для production)

Создать файл сервиса:
```bash
sudo nano /etc/systemd/system/tales.service
```

Вставить содержимое:
```ini
[Unit]
Description=Tales Story Generator Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tales
Environment="PATH=/opt/tales/venv/bin"
ExecStart=/opt/tales/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Сохранить (Ctrl+X, потом Y, потом Enter).

Включить и запустить сервис:
```bash
sudo systemctl daemon-reload
sudo systemctl enable tales
sudo systemctl start tales
```

Проверить статус:
```bash
sudo systemctl status tales
```

Посмотреть логи:
```bash
sudo journalctl -u tales -f
```

## 7. Настройка Nginx как reverse proxy (опционально)

Если хочешь использовать Nginx для проксирования на порт 80:

```bash
sudo apt install -y nginx

# Создать конфиг
sudo nano /etc/nginx/sites-available/tales
```

Вставить:
```nginx
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Включить конфиг:
```bash
sudo ln -s /etc/nginx/sites-available/tales /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 8. Проверка работы

Протестировать endpoint:
```bash
curl -X POST http://YOUR_VPS_IP:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "peer_id": "test_user",
    "message": "Тестовое описание ребенка"
  }'
```

Посмотреть логи:
```bash
sudo journalctl -u tales -f
```

## Полезные команды

```bash
# Перезагрузить сервис
sudo systemctl restart tales

# Остановить сервис
sudo systemctl stop tales

# Просмотреть последние логи
sudo journalctl -u tales -n 100

# Обновить код и перезагрузить
cd /opt/tales && git pull && sudo systemctl restart tales
```
