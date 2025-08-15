import base64
import logging
import os
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


class ImageGenerator:
	def __init__(self,
				api_key: Optional[str] = None,
				model_name: Optional[str] = None,
				size: Optional[str] = None):
		self.api_key = api_key or os.getenv("OPENAI_API_KEY", "").strip()
		self.model_name = model_name or os.getenv("IMAGE_MODEL", "gpt-image-1").strip()
		self.size = size or os.getenv("IMAGE_SIZE", "1024x1024").strip()
		self.disabled = not bool(self.api_key)
		self.client = OpenAI(api_key=self.api_key) if not self.disabled else None

	def generate_image_bytes(self, title: str, summary: str, locale: str = "uk") -> Optional[bytes]:
		"""Generate a news-style illustration. Returns PNG bytes or None on failure."""
		if self.disabled or not self.client:
			return None
		try:
			# Keep prompt concise and safe; avoid text overlays for better clarity in previews
			if locale.lower().startswith("ru"):
				prompt = (
					f"Иллюстрация к новости: {title}. "
					"Стиль: фотореалистичная/иллюстративная подача, без текста на изображении, без водяных знаков. "
					"Четкая композиция, высокий контраст, хорошее освещение, качество — HQ."
				)
			else:
				prompt = (
					f"Ілюстрація до новини: {title}. "
					"Стиль: фотореалістична/ілюстративна подача, без тексту на зображенні, без водяних знаків. "
					"Чітка композиція, високий контраст, хороше освітлення, якість — HQ."
				)
			logger.info(f"Generate image using model: {self.model_name}")
			resp = self.client.images.generate(
				model=self.model_name,
				prompt=prompt,
				size=self.size,
				quality="high",
			)
			b64 = resp.data[0].b64_json
			return base64.b64decode(b64)
		except Exception as exc:
			logger.error("IMAGE generate failed: %s", exc)
			return None


