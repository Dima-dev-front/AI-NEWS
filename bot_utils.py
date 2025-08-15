import logging
import json
from typing import Optional, List, Dict
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)


def _normalize_paragraphs(text: str) -> str:
	# Ensure paragraphs, remove ellipses, indent remark
	if not text:
		return ""
	t = text.replace("\r\n", "\n").replace("\r", "\n").strip()
	# replace three dots variants with a period
	t = t.replace("…", ".").replace("...", ".")
	# collapse multiple blank lines
	lines = [ln.strip() for ln in t.split("\n")]
	paragraphs: List[str] = []
	buf: List[str] = []
	for ln in lines:
		if not ln:
			if buf:
				paragraphs.append(" ".join(buf).strip())
				buf = []
			continue
		buf.append(ln)
	if buf:
		paragraphs.append(" ".join(buf).strip())
	# indent last paragraph as a remark if it looks like one; ensure emoji prefix
	formatted: List[str] = []
	for i, p in enumerate(paragraphs):
		is_last = i == len(paragraphs) - 1
		starts_with_emoji = any(p.startswith(e) for e in ["🙂","😉","🤖","📝","📰","💡","📌","⚠️","✅","❗","ℹ️","📈","📉","🚀"]) or (p[:1].encode('utf-8') != p[:1])
		if is_last:
			remark = p
			if not starts_with_emoji:
				remark = "💡 " + remark
			formatted.append("\t".replace("\t", "  ") + remark)
		else:
			formatted.append(p)
	return "\n\n".join(formatted)


def format_message_html(title: str, summary: str, source_url: str) -> str:
	# Source is intentionally omitted per requirements
	body = _normalize_paragraphs(summary)
	return f"<b>{escape_html(title)}</b>\n\n{escape_html(body)}"


def format_message_plain(title: str, summary: str, source_url: str) -> str:
	# Source is intentionally omitted per requirements
	parts = [title.strip()]
	if summary.strip():
		parts.append("")
		parts.append(_normalize_paragraphs(summary.strip()))
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


def send_to_telegram(bot_token: str, chat_id: str, message_html: str, image_url: Optional[str] = None, message_plain: Optional[str] = None, media: Optional[List[Dict]] = None, image_bytes: Optional[bytes] = None) -> None:
	base_url = f"https://api.telegram.org/bot{bot_token}"

	# If media group provided, try to send as album (up to 10 items)
	if media:
		group = []
		for m in media[:10]:
			try:
				t = (m.get("type") or "").strip().lower()
				u = (m.get("url") or "").strip()
				if not u:
					continue
				if t == "video":
					group.append({"type": "video", "media": u})
				else:
					group.append({"type": "photo", "media": u})
			except Exception:
				continue
		if group and len(group) >= 2:
			try:
				cap = message_html
				if len(cap) > 1024:
					cap = cap[:1024]
				group[0]["caption"] = cap
				group[0]["parse_mode"] = "HTML"
				payload = {"chat_id": chat_id, "media": json.dumps(group)}
				resp = requests.post(f"{base_url}/sendMediaGroup", data=payload, timeout=20)
				resp.raise_for_status()
				logger.info("Sent media group to Telegram.")
				return
			except Exception as exc:
				logger.error("Telegram sendMediaGroup failed: %s", exc)
				# fall back to single
	# Prefer sending photo with HTML caption when image is available
	if image_url:
		caption = message_html
		if len(caption) > 1024:
			caption = caption[:1024]
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
					plain_cap = plain_cap[:1024]
				photo_payload["caption"] = plain_cap
				resp = requests.post(f"{base_url}/sendPhoto", data=photo_payload, timeout=15)
			resp.raise_for_status()
			logger.info("Sent photo with caption to Telegram.")
			return
		except Exception as exc:
			logger.error("Telegram sendPhoto failed: %s", exc)
			# Fall through to text-only

	# If we have raw image bytes (AI generated), upload via multipart
	if image_bytes:
		try:
			caption = message_html
			if len(caption) > 1024:
				caption = caption[:1024]
			files = {"photo": ("image.png", image_bytes, "image/png")}
			data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
			resp = requests.post(f"{base_url}/sendPhoto", data=data, files=files, timeout=20)
			resp.raise_for_status()
			logger.info("Sent generated image with caption to Telegram.")
			return
		except Exception as exc:
			logger.error("Telegram sendPhoto(bytes) failed: %s", exc)
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
