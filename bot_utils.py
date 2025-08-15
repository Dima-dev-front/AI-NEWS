import logging
import json
from typing import Optional, List, Dict
from urllib.parse import quote, urlparse, parse_qs, urlencode, urlunparse

import requests
import os

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


def _normalize_media_url(url: str) -> str:
	"""Normalize media URL to dedupe similar resources (strip common size/tracking params)."""
	try:
		o = urlparse(url)
		qs = parse_qs(o.query, keep_blank_values=True)
		# Remove common size/tracking params
		blocked = {"utm_source","utm_medium","utm_campaign","utm_term","utm_content","utm_id","gclid","fbclid","igshid","ref","ref_src","ref_url","ncid","spm","w","width","h","height","sz","s","name"}
		qs = {k:v for k,v in qs.items() if k not in blocked}
		new_query = urlencode({k:(v[0] if isinstance(v, list) and v else v) for k,v in qs.items()}, doseq=False)
		o = o._replace(query=new_query)
		# Drop trailing slash
		if o.path.endswith("/") and len(o.path) > 1:
			o = o._replace(path=o.path.rstrip("/"))
		return urlunparse(o)
	except Exception:
		return url


def _is_high_quality_image(url: str, min_bytes: int = 15000, timeout: int = 5) -> bool:
	"""Quick HEAD check to ensure the image is not a tiny thumbnail."""
	try:
		r = requests.head(url, timeout=timeout, allow_redirects=True)
		ct = (r.headers.get("Content-Type") or "").lower()
		if "image" not in ct:
			return False
		length = r.headers.get("Content-Length")
		if length and length.isdigit():
			return int(length) >= min_bytes
		# No length header — assume OK
		return True
	except Exception:
		return False


def _filter_and_dedupe_media(media: Optional[List[Dict]]) -> List[Dict]:
	if not media:
		return []
	seen: set[str] = set()
	result: List[Dict] = []
	for m in media:
		try:
			t = (m.get("type") or "").strip().lower()
			u = (m.get("url") or "").strip()
			if not u or t not in ("photo","video"):
				continue
			norm = _normalize_media_url(u)
			if norm in seen:
				continue
			if t == "photo" and not _is_high_quality_image(u):
				continue
			seen.add(norm)
			result.append({"type": t, "url": u})
		except Exception:
			continue
	return result


def send_to_telegram(bot_token: str, chat_id: str, message_html: str, image_url: Optional[str] = None, message_plain: Optional[str] = None, media: Optional[List[Dict]] = None, image_bytes: Optional[bytes] = None) -> None:
	base_url = f"https://api.telegram.org/bot{bot_token}"

	# Prepare single caption (title + summary) within Telegram limit
	caption_full = message_html
	if len(caption_full) > 1024:
		caption_full = caption_full[:1024]

	# Filter and dedupe media to avoid duplicates and low-quality images
	if media:
		media = _filter_and_dedupe_media(media)

	# If media group provided, try to send as album (up to 10 items)
	if media:
		group = []
		for m in media[:4]:
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
				group[0]["caption"] = caption_full
				group[0]["parse_mode"] = "HTML"
				payload = {"chat_id": chat_id, "media": json.dumps(group)}
				resp = requests.post(f"{base_url}/sendMediaGroup", data=payload, timeout=20)
				resp.raise_for_status()
				logger.info("Sent media group to Telegram.")
				return
			except Exception as exc:
				logger.error("Telegram sendMediaGroup failed: %s", exc)
				# fall back to single
		elif group and len(group) == 1 and not image_url:
			one = group[0]
			try:
				if one.get("type") == "photo":
					payload = {"chat_id": chat_id, "photo": one.get("media"), "caption": caption_full, "parse_mode": "HTML"}
					resp = requests.post(f"{base_url}/sendPhoto", data=payload, timeout=15)
					resp.raise_for_status()
				elif one.get("type") == "video":
					payload = {"chat_id": chat_id, "video": one.get("media"), "caption": caption_full, "parse_mode": "HTML"}
					resp = requests.post(f"{base_url}/sendVideo", data=payload, timeout=20)
					resp.raise_for_status()
				return
			except Exception as exc:
				logger.error("Telegram send single media failed: %s", exc)

	# Prefer sending photo with HTML caption when image is available
	if image_url:
		caption = caption_full
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
				plain_cap = (message_plain or "")[:1024]
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
			caption = caption_full
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


def build_screenshot_url(page_url: str, provider: str = None, width: int = None) -> Optional[str]:
	"""Return a screenshot image URL for the given page using a simple provider.

	Providers:
	- mshots (default): https://s.wordpress.com/mshots/v1/<url>?w=<width>
	- thumio: https://image.thum.io/get/width/<width>/<url>
	"""
	try:
		provider = (provider or os.getenv("SCREENSHOT_PROVIDER", "mshots")).strip().lower()
		width = int(os.getenv("SCREENSHOT_WIDTH", str(width or 1200)))
		enc = quote(page_url, safe="")
		if provider == "thumio":
			return f"https://image.thum.io/get/width/{width}/{enc}"
		# default mshots
		return f"https://s.wordpress.com/mshots/v1/{enc}?w={width}"
	except Exception:
		return None
