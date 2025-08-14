import logging
from typing import Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)


def format_message_html(title: str, summary: str, source_url: str) -> str:
	# Source is intentionally omitted per requirements
	return f"<b>{escape_html(title)}</b>\n\n{escape_html(summary)}"


def format_message_plain(title: str, summary: str, source_url: str) -> str:
	# Source is intentionally omitted per requirements
	parts = [title.strip()]
	if summary.strip():
		parts.append("")
		parts.append(summary.strip())
	text = "\n".join(parts).strip()
	return text[:4000]


def sanitize_url(url: str) -> str:
	try:
		return quote(url, safe=":/#?&=@[]!$&'()*+,;%")
	except Exception:
		return url


def escape_html(text: str) -> str:
	return (
		text.replace("&", "&amp;")
		.replace("<", "&lt;")
		.replace(">", "&gt;")
		.replace('"', "&quot;")
	)


def send_to_telegram(bot_token: str, chat_id: str, message_html: str, image_url: Optional[str] = None, message_plain: Optional[str] = None) -> None:
	base_url = f"https://api.telegram.org/bot{bot_token}"

	# Prefer sending photo with HTML caption when image is available
	if image_url:
		caption = message_html
		if len(caption) > 1024:
			caption = caption[:1021] + "..."
		photo_payload = {
			"chat_id": chat_id,
			"photo": image_url,
			"caption": caption,
			"parse_mode": "HTML",
		}
		try:
			resp = requests.post(f"{base_url}/sendPhoto", data=photo_payload, timeout=15)
			if resp.status_code == 400 and message_plain:
				# Fallback to plain caption
				photo_payload.pop("parse_mode", None)
				plain_cap = message_plain
				if len(plain_cap) > 1024:
					plain_cap = plain_cap[:1021] + "..."
				photo_payload["caption"] = plain_cap
				resp = requests.post(f"{base_url}/sendPhoto", data=photo_payload, timeout=15)
			resp.raise_for_status()
			logger.info("Sent photo with caption to Telegram.")
			return
		except Exception as exc:
			logger.error("Telegram sendPhoto failed: %s", exc)
			# Fall through to text-only

	# Text-only message
	payload_html = {
		"chat_id": chat_id,
		"text": message_html,
		"parse_mode": "HTML",
		"disable_web_page_preview": False,
	}
	try:
		resp = requests.post(f"{base_url}/sendMessage", data=payload_html, timeout=15)
		if resp.status_code != 200:
			logger.error("Telegram sendMessage(HTML) error %s: %s", resp.status_code, resp.text)
			if message_plain and resp.status_code == 400:
				payload_plain = {
					"chat_id": chat_id,
					"text": message_plain,
					"disable_web_page_preview": False,
				}
				resp2 = requests.post(f"{base_url}/sendMessage", data=payload_plain, timeout=15)
				resp2.raise_for_status()
			else:
				resp.raise_for_status()
	except Exception as exc:
		logger.error("Telegram send failed: %s", exc)
		raise
