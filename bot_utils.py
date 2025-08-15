import logging
from typing import Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)


def format_summary_with_structure(summary: str, html: bool = True) -> str:
	"""
	Format summary with proper structure, indentation for comments/jokes with icons
	"""
	if not summary:
		return ""
	
	lines = summary.split('\n')
	formatted_lines = []
	
	for line in lines:
		line = line.strip()
		if not line:
			formatted_lines.append("")
			continue
			
		# Detect if this is a comment/joke line (typically the last sentence or contains humor indicators)
		is_comment = (
			# Check for typical joke/comment patterns
			any(indicator in line.lower() for indicator in [
				'хоча', 'втім', 'до речі', 'цікаво', 'схоже', 'мабуть', 'очевидно', 
				'зрештою', 'принаймні', 'однак', 'проте', 'але ж', 'звісно',
				'😄', '😅', '🤔', '🙃', '😏', '🤷', '💭', '🎯'
			]) or
			# Check if it's likely a witty remark (short sentence with certain patterns)
			(len(line.split()) <= 15 and any(word in line.lower() for word in [
				'не варто', 'краще', 'гірше', 'дивно', 'чудово', 'жахливо', 'смішно'
			]))
		)
		
		if is_comment:
			# Add appropriate icon based on content context
			icon = get_context_icon(line)
			if html:
				formatted_line = f"    {icon} <i>{escape_html(line)}</i>"
			else:
				formatted_line = f"    {icon} {line}"
		else:
			# Regular content line
			if html:
				formatted_line = escape_html(line)
			else:
				formatted_line = line
		
		formatted_lines.append(formatted_line)
	
	# Join lines and add proper paragraph separation
	result = '\n'.join(formatted_lines)
	
	# Add paragraph breaks for better readability
	result = result.replace('\n\n\n', '\n\n')  # Normalize multiple breaks
	
	return result


def get_context_icon(text: str) -> str:
	"""
	Select appropriate icon based on text content
	"""
	text_lower = text.lower()
	
	# Technology/AI related
	if any(word in text_lower for word in ['штучний інтелект', 'ай', 'ші', 'технологі', 'алгоритм', 'робот', 'автоматизаці']):
		return '🤖'
	
	# Money/business related  
	if any(word in text_lower for word in ['гроші', 'долар', 'інвестиці', 'прибуток', 'бізнес', 'компані', 'стартап']):
		return '💰'
	
	# Surprise/shock
	if any(word in text_lower for word in ['несподівано', 'шокуюч', 'вражаюч', 'дивно', 'неймовірно']):
		return '😲'
	
	# Positive/success
	if any(word in text_lower for word in ['чудово', 'відмінно', 'успішно', 'перемог', 'досягнення']):
		return '🎉'
	
	# Negative/concern
	if any(word in text_lower for word in ['проблем', 'загроз', 'небезпек', 'кризи', 'жахлив']):
		return '⚠️'
	
	# Thinking/analysis
	if any(word in text_lower for word in ['думк', 'аналіз', 'дослідженн', 'вивчен', 'з\'ясуван']):
		return '🤔'
	
	# Fun/entertainment
	if any(word in text_lower for word in ['смішно', 'весело', 'кумедно', 'жарт', 'гумор']):
		return '😄'
	
	# Default thinking icon for comments
	return '💭'


def format_message_html(title: str, summary: str, source_url: str) -> str:
	# Source is intentionally omitted per requirements
	formatted_summary = format_summary_with_structure(summary)
	return f"<b>{escape_html(title)}</b>\n\n{formatted_summary}"


def format_message_plain(title: str, summary: str, source_url: str) -> str:
	# Source is intentionally omitted per requirements
	parts = [title.strip()]
	if summary.strip():
		parts.append("")
		formatted_summary = format_summary_with_structure(summary, html=False)
		parts.append(formatted_summary.strip())
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


def send_to_telegram(bot_token: str, chat_id: str, message_html: str, image_url: Optional[str] = None, message_plain: Optional[str] = None, all_media: Optional[list] = None) -> None:
	base_url = f"https://api.telegram.org/bot{bot_token}"
	
	# Filter media to only images and videos, limit to avoid telegram limits
	filtered_media = []
	if all_media:
		for media_url in all_media[:10]:  # Telegram allows up to 10 items in media group
			if media_url and media_url.startswith('http'):
				# Simple check for image/video extensions
				lower_url = media_url.lower()
				if any(ext in lower_url for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.mov', '.avi']):
					filtered_media.append(media_url)
	
	# Try to send media group if we have multiple media items
	if len(filtered_media) > 1:
		try:
			media_group = []
			caption = message_html if len(message_html) <= 1024 else message_html[:1021] + "..."
			
			for i, media_url in enumerate(filtered_media[:10]):  # Telegram limit
				media_item = {
					"type": "photo",  # Default to photo, Telegram will handle videos
					"media": media_url
				}
				# Add caption only to the first item
				if i == 0:
					media_item["caption"] = caption
					media_item["parse_mode"] = "HTML"
				media_group.append(media_item)
			
			import json as json_lib
			media_payload = {
				"chat_id": chat_id,
				"media": json_lib.dumps(media_group)
			}
			
			resp = requests.post(f"{base_url}/sendMediaGroup", data=media_payload, timeout=15)
			if resp.status_code == 200:
				logger.info("Sent media group with %d items to Telegram.", len(filtered_media))
				return
			else:
				logger.warning("Media group failed, falling back to single photo: %s", resp.text)
		except Exception as exc:
			logger.warning("Media group send failed, falling back: %s", exc)

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
