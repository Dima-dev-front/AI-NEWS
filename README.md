## AI-NEWS Telegram Bot

Автоматический постинг новостей в Telegram-канал с умными резюме от ИИ. Бот проверяет RSS-фиды каждые 30 минут и публикует самые интересные новости.

### ✨ Особенности
- 🤖 **Умная обработка** - ИИ выбирает 1 лучшую новость и резюмирует ее
- 🎨 **ИИ-генерация изображений** - автоматически создает уникальные изображения с помощью DALL-E
- ⚡ **Автоматический постинг** - каждые 30 минут без участия пользователя
- 🎯 **GitHub Actions** - автозапуск при каждом пуше в main
- 📱 **Rich-контент** - поддержка изображений и видео
- 🔄 **Дедупликация** - избегает повторных постов
- ✨ **Красивое форматирование** - эмодзи и структурированный текст

### 🚀 Быстрый старт (локально)

1. **Настройте переменные окружения** в `.env`:
```env
# Обязательные
TELEGRAM_TOKEN=your_bot_token
CHAT_ID=your_chat_id
OPENAI_API_KEY=your_openai_key
RSS_FEEDS=https://feed1.com/rss,https://feed2.com/rss

# Опциональные
MODEL_NAME=gpt-4o-mini
NEWS_QUERY=Украина
CHECK_INTERVAL_MIN=30
POST_DELAY_SEC=60
MAX_POSTS_PER_CYCLE=1
LOCALE=ru
COUNTRY=RU
REQUIRE_MEDIA=1
GENERATE_AI_IMAGES=1
```

2. **Установите зависимости**:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

3. **Запуск**:
```bash
python bot.py
```

### 🐳 Docker

```bash
docker build -t ai-news-bot .
docker run --name ai-news --env-file .env --restart unless-stopped ai-news-bot
```

### 🔄 GitHub Actions (автоматический режим)

Бот автоматически запускается через GitHub Actions:
- **📅 По расписанию**: каждый час
- **🚀 При пуше в main**: автоматически при обновлении кода
- **👆 Вручную**: через интерфейс GitHub Actions

Настройте секреты в GitHub:
- `TELEGRAM_TOKEN`
- `CHAT_ID` 
- `OPENAI_API_KEY`
- `LLM_PROVIDER`
- `MODEL_NAME`

И переменную `RSS_FEEDS` в Variables.

### ⚙️ Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `TELEGRAM_TOKEN` | - | Токен Telegram бота (обязательно) |
| `CHAT_ID` | - | ID чата/канала для постинга (обязательно) |
| `OPENAI_API_KEY` | - | Ключ OpenAI API (обязательно) |
| `RSS_FEEDS` | - | RSS-фиды через запятую (обязательно) |
| `MODEL_NAME` | `gpt-4o-mini` | Модель ИИ для резюмирования |
| `NEWS_QUERY` | `Украина` | Поисковый запрос для фильтрации |
| `CHECK_INTERVAL_MIN` | `30` | Интервал проверки новостей (минуты) |
| `POST_DELAY_SEC` | `60` | Задержка между постами (секунды) |
| `MAX_POSTS_PER_CYCLE` | `1` | Максимум постов за один цикл |
| `REQUIRE_MEDIA` | `1` | Требовать изображения/видео |
| `GENERATE_AI_IMAGES` | `1` | Генерировать изображения с помощью DALL-E |
| `RUN_ONCE` | `0` | Запустить один раз и выйти |
| `LOCALE` | `ru` | Локаль для поиска |
| `COUNTRY` | `RU` | Код страны для поиска |

### 📁 Архитектура

- `bot.py` — основной цикл и планировщик постинга
- `news.py` — загрузка и обработка RSS-фидов
- `summarizer.py` — ИИ-резюмирование и выбор лучших новостей
- `bot_utils.py` — отправка в Telegram и форматирование
- `data/published.json` — кеш опубликованных новостей
- `data/recent_titles.json` — дедупликация по заголовкам
- `.github/workflows/ai-news.yml` — GitHub Actions workflow
