import logging
import os
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


class Summarizer:
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        # Provider selection: 'xai', 'groq', 'openai', or 'auto' (default)
        provider_env = os.getenv("LLM_PROVIDER", "auto").strip().lower()
        xai_key_env = os.getenv("XAI_API_KEY", "").strip()
        groq_key_env = os.getenv("GROQ_API_KEY", "").strip()

        if provider_env == "xai" or (provider_env == "auto" and xai_key_env):
            # xAI (Grok) via OpenAI-compatible endpoint
            self.provider = "xai"
            self.api_key = api_key or xai_key_env
            self.model_name = model_name or os.getenv("MODEL_NAME", "grok-2-latest")
            self.base_url = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").strip()
            self.disabled = not bool(self.api_key)
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url) if not self.disabled else None
        elif provider_env == "groq" or (provider_env == "auto" and groq_key_env):
            # Groq via OpenAI-compatible endpoint
            self.provider = "groq"
            self.api_key = api_key or groq_key_env
            self.model_name = model_name or os.getenv("MODEL_NAME", "llama-3.1-8b-instant")
            self.base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()
            self.disabled = not bool(self.api_key)
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url) if not self.disabled else None
        else:
            # Default: OpenAI
            self.provider = "openai"
            self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
            self.model_name = model_name or os.getenv("MODEL_NAME", "gpt-4o-mini")
            self.disabled = os.getenv("DISABLE_OPENAI", "").lower() in ("1", "true", "yes", "on") or not bool(self.api_key)
            self.client = OpenAI(api_key=self.api_key) if (self.api_key and not self.disabled) else None

    def summarize(self, title: str, url: str) -> str:
        if self.disabled or not self.client:
            return ""
        prompt = (
            "Ти — помічник-редактор новин. Поверни результат СТРОГО у форматі JSON без пояснень, з ключами 'title', 'summary' українською мовою, і опційним 'cta_url'. "
            "'title' — короткий заголовок (до 90 символів). "
            "'summary' — 3–5 речень: стисни головну новину, наведи ключові факти і мінімальний контекст, без води, без емодзі, без HTML. "
            "ОСТАННЄ речення — коротка доречна дотепна ремарка (1 коротке речення, без образ і політики). "
            "'cta_url' — повний https:// посилання на сторінку 'Спробувати/Демо/Почати/Sign up/Get started/Download', якщо в матеріалі явно присутнє таке посилання; якщо ні — null.\n\n"
            f"Заголовок оригіналу: {title}\nДжерело: {url}\n\nВивід (ЛИШЕ JSON):"
        )
        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Ти — україномовний редактор новин. Відповідаєш ЛИШЕ валідним компактним JSON без трійних лапок і без пояснень. 'summary' має містити 3–5 речень і завершуватися короткою дотепною ремаркою."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.35,
                max_tokens=360,
            )
            text = completion.choices[0].message.content.strip()
            return text
        except Exception as exc:
            logger.error("%s summarize failed: %s", self.provider.upper(), exc)
            return ""
