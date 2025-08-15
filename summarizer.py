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
            self.model_name = model_name or os.getenv("MODEL_NAME") or "grok-2-latest"
            self.base_url = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").strip()
            self.disabled = not bool(self.api_key)
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url) if not self.disabled else None
        elif provider_env == "groq" or (provider_env == "auto" and groq_key_env):
            # Groq via OpenAI-compatible endpoint
            self.provider = "groq"
            self.api_key = api_key or groq_key_env
            self.model_name = model_name or os.getenv("MODEL_NAME") or "llama-3.1-8b-instant"
            self.base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()
            self.disabled = not bool(self.api_key)
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url) if not self.disabled else None
        else:
            # Default: OpenAI
            self.provider = "openai"
            self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
            self.model_name = model_name or os.getenv("MODEL_NAME") or "gpt-4o-mini"
            self.disabled = os.getenv("DISABLE_OPENAI", "").lower() in ("1", "true", "yes", "on") or not bool(self.api_key)
            self.client = OpenAI(api_key=self.api_key) if (self.api_key and not self.disabled) else None

    def summarize(self, title: str, url: str) -> str:
        if self.disabled or not self.client:
            return ""
        prompt = (
            "Ти — професійний редактор новин. Поверни результат СТРОГО у форматі JSON без пояснень, з ключами 'title', 'summary' українською мовою, і опційним 'cta_url'. "
            "'title' — короткий заголовок (до 90 символів). "
            "'summary' — структурована новина з 3–5 речень у новинному стилі:\n"
            "- Пиши як НОВИНУ, а не як переказ ('компанія оголосила', 'відбулася подія', 'з'явилася інформація')\n"
            "- НЕ використовуй '...', 'автор говорить', 'у статті зазначається', 'за словами'\n" 
            "- Подавай факти прямо та конкретно\n"
            "- Кожне речення має містити конкретну інформацію\n"
            "- ОСТАННЄ речення — ОБОВ'ЯЗКОВО коротка доречна дотепна ремарка або коментар (максимум 10 слів, без образ і політики)\n"
            "- Без емодзі, без HTML, новинний стиль\n"
            "- Розділяй абзаци символом \\n для кращої читабельності\n"
            "'cta_url' — повний https:// посилання на сторінку 'Спробувати/Демо/Почати/Sign up/Get started/Download', якщо в матеріалі явно присутнє таке посилання; якщо ні — null.\n\n"
            f"Заголовок оригіналу: {title}\nДжерело: {url}\n\nВивід (ЛИШЕ JSON):"
        )
        try:
            logger.info(f"Summarize using model: {self.model_name}")
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Ти — професійний редактор новин. Відповідаєш ЛИШЕ валідним JSON без трійних лапок і пояснень. Пиши новини у прямому стилі, без переказу. 'summary' містить 3–5 речень + ОБОВ'ЯЗКОВО коротку дотепну ремарку в кінці (максимум 10 слів). Використовуй \\n для абзаців."},
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

    def select_best(self, items: list[dict]) -> list[int]:
        """Return list with index (0-based) of the single best news item.

        Each item is expected to have keys: 'title' and optional 'link'.
        Returns list with 1 element - index of the best news item.
        """
        if self.disabled or not self.client or not items:
            return []
        # Prepare compact numbered list to keep tokens low
        lines = []
        for idx, it in enumerate(items[:20]):
            title = str(it.get("title") or "").strip()
            link = str(it.get("link") or "").strip()
            domain = ""
            try:
                from urllib.parse import urlparse
                domain = urlparse(link).netloc or ""
            except Exception:
                domain = ""
            line = f"{idx}. {title}" + (f" — {domain}" if domain else "")
            lines.append(line)
        list_text = "\n".join(lines)
        prompt = (
            "Ти — головний редактор новин. З наведеного списку обери 1 НАЙКРАЩУ новину, \n"
            "враховуючи глобальну важливість, актуальність, потенційний вплив на ІТ/ШІ, \n"
            "та цікавість для широкої аудitorії. Виведи ЛИШЕ валідний JSON без пояснень у форматі \n"
            "{\"best\": [i]} де i — це індекс найкращої новини зі списку нижче (0‑based). \n"
            "Обирай найякісніший та найцікавіший матеріал. Без зайвого тексту.\n\n"
            f"Список:\n{list_text}\n\nВідповідь (ЛИШЕ JSON):"
        )
        try:
            logger.info(f"Select_best using model: {self.model_name}")
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Ти головний редактор новин. Обираєш 1 найкращу новину з списку. Відповідаєш ТІЛЬКИ валідним JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=200,
            )
            text = completion.choices[0].message.content.strip()
            import json as _json
            try:
                obj = _json.loads(text)
                best = obj.get("best") if isinstance(obj, dict) else None
                if isinstance(best, list):
                    # keep valid indices and preserve order
                    result = []
                    for v in best:
                        try:
                            i = int(v)
                            if 0 <= i < len(items) and i not in result:
                                result.append(i)
                        except Exception:
                            continue
                    return result
            except Exception:
                return []
            return []
        except Exception as exc:
            logger.error("%s select_best failed: %s", self.provider.upper(), exc)
            return []
