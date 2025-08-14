## AI-NEWS Telegram Bot

Автопостинг новостей из Google News в Telegram-канал с кратким резюме от OpenAI.

### Быстрый старт (локально)
1. Создайте `.env` c ключами: `OPENAI_API_KEY`, `TELEGRAM_TOKEN`, `CHAT_ID`, `NEWS_QUERY` (и при необходимости `MODEL_NAME`, `CHECK_INTERVAL_MIN`, `POST_DELAY_SEC`, `FALLBACK_IMAGE_URL`, `LOCALE`, `COUNTRY`).
2. Установите зависимости:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
3. Запуск:
```bash
python bot.py
```

### Docker
```bash
docker build -t ai-news-bot .
docker run --name ai-news --env-file .env --restart unless-stopped ai-news-bot
```

### Архитектура
- `bot.py` — основной цикл и планировщик
- `news.py` — загрузка новостей из Google News RSS
- `summarizer.py` — сжатие через OpenAI
- `bot_utils.py` — Telegram и обработка изображений
- `data/published.json` — уже опубликованные ссылки
