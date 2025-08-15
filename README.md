## AI-NEWS Telegram Bot

Автоматический постинг новостей в Telegram-канал с умными резюме от ИИ. Бот проверяет RSS-фиды каждые 30 минут и публикует самые интересные новости.

### ✨ Особенности
- 🤖 **Умная обработка** - ИИ выбирает 1 лучшую новость и резюмирует ее
- 🎨 **ИИ-генерация изображений** - опционально создает уникальные изображения с помощью DALL-E (отключено по умолчанию)
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
RSS_FEEDS=https://www.wired.com/feed/tag/ai/latest/rss,https://www.technologyreview.com/feed/,https://deepmind.google/blog/rss.xml,https://thegradient.pub/feed/,https://www.sciencedaily.com/rss/all.xml

# Опциональные
MODEL_NAME=gpt-4o-mini
NEWS_QUERY=Украина
CHECK_INTERVAL_MIN=30
POST_DELAY_SEC=60
MAX_POSTS_PER_CYCLE=1
LOCALE=ru
COUNTRY=RU
REQUIRE_MEDIA=1
GENERATE_AI_IMAGES=0
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

### 📡 Рекомендуемые RSS-фиды

Для получения качественных новостей по ИИ, технологиям и науке используйте этот список:

```
https://www.wired.com/feed/tag/ai/latest/rss,https://www.technologyreview.com/feed/,https://deepmind.google/blog/rss.xml,https://thegradient.pub/feed/,https://towardsdatascience.com/feed/,https://www.sciencedaily.com/rss/computers_math/artificial_intelligence.xml,https://news.mit.edu/topic/mitartificial-intelligence2-rss.xml,https://www.theguardian.com/technology/artificialintelligenceai/rss,https://techcrunch.com/category/artificial-intelligence/feed/,https://venturebeat.com/category/ai/feed/,https://www.marktechpost.com/feed/,https://www.analyticsvidhya.com/feed/,https://www.nasa.gov/news-release/feed/,https://www.nasa.gov/feeds/iotd-feed/,https://www.jpl.nasa.gov/feeds/news/,https://www.sciencenews.org/feed,https://www.newscientist.com/section/news/feed/,https://www.sciencedaily.com/rss/all.xml,https://www.space.com/feeds/all
```

**Источники включают:**
- 🤖 **ИИ и машинное обучение**: Wired AI, MIT Tech Review, DeepMind, The Gradient
- 🔬 **Научные публикации**: Science Daily, Science News, New Scientist
- 🚀 **Космос и NASA**: NASA News, NASA Image of the Day, JPL News, Space.com
- 💻 **Технологические медиа**: TechCrunch, VentureBeat, The Guardian Tech
- 📚 **Образовательные ресурсы**: Towards Data Science, Analytics Vidhya, MarkTechPost

**Логика работы:**
1. Бот проходит по всем RSS-фидам в указанном порядке
2. Из каждого фида берет до 3-5 новостей (настраивается)
3. ИИ выбирает 1 лучшую новость из всех собранных
4. Публикует выбранную новость в Telegram

**⚠️ Исключенные источники:**
- `aitrends.com` - HTTP 503 ошибки
- `machinelearningmastery.com` - HTTP 403 блокировка
- `aiwire.net` - HTTP 403 блокировка  
- `spacenews.com` - HTTP 429 rate limiting

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
| `GENERATE_AI_IMAGES` | `0` | Генерировать изображения с помощью DALL-E |
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
