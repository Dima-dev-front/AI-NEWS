## AI-NEWS Telegram Bot

Автопостинг новостей в Telegram-канал с кратким резюме от OpenAI. Источники: RSS (по списку фидов) или AI‑поиск (SerpAPI Google News).

### Быстрый старт (локально)
1. Создайте `.env` c ключами: `OPENAI_API_KEY`, `TELEGRAM_TOKEN`, `CHAT_ID` (и при необходимости `MODEL_NAME`, `CHECK_INTERVAL_MIN`, `POST_DELAY_SEC`, `FALLBACK_IMAGE_URL`, `LOCALE`, `COUNTRY`).
   - Режимы источников:
     - `DISCOVERY_MODE=rss` и `RSS_FEEDS="https://example.com/feed.xml,https://example.org/rss"`
     - либо `DISCOVERY_MODE=search`, `SEARCH_PROVIDER=serpapi`, `SERPAPI_API_KEY=...`, `DISCOVERY_QUERY="artificial intelligence news last 24 hours"`
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
- `news.py` — загрузка новостей из RSS, каноникализация и метаданные страниц
- `search.py` — AI/веб‑поиск ссылок (SerpAPI Google News)
- `summarizer.py` — сжатие через OpenAI
- `bot_utils.py` — Telegram и обработка изображений
- `data/published.json` — уже опубликованные ссылки
