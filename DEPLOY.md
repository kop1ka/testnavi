# Как открыть проект с любой точки мира

Этот проект можно развернуть и сделать доступным из любой точки мира несколькими способами:

## 🚀 Быстрый старт

### Вариант 1: Docker (Рекомендуется)

```bash
# Сборка и запуск через docker-compose
docker-compose up -d --build

# Приложение будет доступно по адресу: http://localhost:5000
```

### Вариант 2: Прямой запуск Python

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск сервера
python app.py

# Приложение будет доступно по адресу: http://0.0.0.0:5000
```

---

## 🌍 Публикация в интернете

### Способ 1: Ngrok (Быстрый временный доступ)

```bash
# Установите ngrok: https://ngrok.com/download
ngrok http 5000
```
После запуска вы получите публичный URL вида `https://xxxx-xxxx.ngrok.io`

### Способ 2: Cloudflare Tunnel (Бесплатно и безопасно)

```bash
# Установите cloudflared
# Запустите туннель
cloudflared tunnel --url http://localhost:5000
```

### Способ 3: Развёртывание на VPS сервере

1. Арендуйте сервер (DigitalOcean, Hetzner, AWS, etc.)
2. Установите Docker и Docker Compose
3. Скопируйте проект на сервер
4. Запустите: `docker-compose up -d`
5. Настройте домен и SSL через Nginx + Let's Encrypt

### Способ 4: Платформы для деплоя

- **Render.com** - бесплатный хостинг для веб-приложений
- **Railway.app** - простой деплой с GitHub
- **Fly.io** - глобальное развёртывание
- **PythonAnywhere** - специализированный Python-хостинг

---

## 🔐 Безопасность при публикации

Перед публикацией в интернете:

1. Измените `SECRET_KEY` в `config/settings.py` на случайную строку
2. Смените пароли пользователей по умолчанию
3. Используйте HTTPS (SSL сертификат)
4. Настройте firewall для ограничения доступа

---

## 📦 Docker команды

```bash
# Сборка образа
docker build -t my-flask-app .

# Запуск контейнера
docker run -p 5000:5000 -v $(pwd)/data:/app/data my-flask-app

# Остановка контейнера
docker-compose down

# Просмотр логов
docker-compose logs -f
```

---

## ⚙️ Конфигурация

Для production окружения настройте переменные:

```bash
export FLASK_ENV=production
export SECRET_KEY=ваш-секретный-ключ
```

Или используйте `.env` файл с `docker-compose`.
