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
	
	# Split by sentences to better detect the final comment/joke
	sentences = []
	temp_sentence = ""
	
	for char in summary:
		temp_sentence += char
		if char in '.!?':
			sentences.append(temp_sentence.strip())
			temp_sentence = ""
	
	if temp_sentence.strip():
		sentences.append(temp_sentence.strip())
	
	if not sentences:
		return summary
	
	# The last sentence is likely a comment/joke if it contains humor indicators
	formatted_sentences = []
	
	for i, sentence in enumerate(sentences):
		is_last = (i == len(sentences) - 1)
		
		# Detect if this is a comment/joke line
		is_comment = (
			is_last and (
				# Check for typical joke/comment patterns
				any(indicator in sentence.lower() for indicator in [
					'хоча', 'втім', 'до речі', 'цікаво', 'схоже', 'мабуть', 'очевидно', 
					'зрештою', 'принаймні', 'однак', 'проте', 'але ж', 'звісно',
					'не варто', 'краще', 'гірше', 'дивно', 'чудово', 'жахливо', 'смішно',
					'😄', '😅', '🤔', '🙃', '😏', '🤷', '💭', '🎯'
				]) or
				# Short witty sentence patterns
				len(sentence.split()) <= 12
			)
		)
		
		if is_comment and is_last:
			# Add appropriate icon and formatting for the final comment
			icon = get_context_icon(sentence)
			if html:
				formatted_sentence = f"\n\n    {icon} <i>{escape_html(sentence)}</i>"
			else:
				formatted_sentence = f"\n\n    {icon} {sentence}"
		else:
			# Regular sentence
			if html:
				formatted_sentence = escape_html(sentence)
			else:
				formatted_sentence = sentence
		
		formatted_sentences.append(formatted_sentence)
	
	# Join sentences, but handle the special formatting for comments
	result = ""
	for i, sentence in enumerate(formatted_sentences):
		if i == 0:
			result += sentence
		elif sentence.startswith('\n\n    '):  # This is a comment
			result += sentence
		else:
			result += " " + sentence
	
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
	
	# Select best media: prioritize videos over images
	best_media_url = None
	if all_media:
		# First, look for videos (higher priority)
		for media_url in all_media:
			if media_url and media_url.startswith('http'):
				lower_url = media_url.lower()
				if any(ext in lower_url for ext in ['.mp4', '.mov', '.avi', '.webm', '.mkv']):
					best_media_url = media_url
					break
		
		# If no video found, look for images
		if not best_media_url:
			for media_url in all_media:
				if media_url and media_url.startswith('http'):
					lower_url = media_url.lower()
					if any(ext in lower_url for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
						best_media_url = media_url
						break
	
	# Use best_media_url if found, otherwise fallback to image_url
	final_media_url = best_media_url or image_url

	# Send media with caption if available
	if final_media_url:
		caption = message_html
		if len(caption) > 1024:
			caption = caption[:1021] + "..."
		
		# Determine if it's a video or photo
		lower_url = final_media_url.lower()
		is_video = any(ext in lower_url for ext in ['.mp4', '.mov', '.avi', '.webm', '.mkv'])
		
		media_payload = {
			"chat_id": chat_id,
			"caption": caption,
			"parse_mode": "HTML",
		}
		
		if is_video:
			media_payload["video"] = final_media_url
			endpoint = "sendVideo"
		else:
			media_payload["photo"] = final_media_url
			endpoint = "sendPhoto"
		
		try:
			resp = requests.post(f"{base_url}/{endpoint}", data=media_payload, timeout=15)
			if resp.status_code == 400 and message_plain:
				# Fallback to plain caption
				media_payload.pop("parse_mode", None)
				plain_cap = message_plain
				if len(plain_cap) > 1024:
					plain_cap = plain_cap[:1021] + "..."
				media_payload["caption"] = plain_cap
				resp = requests.post(f"{base_url}/{endpoint}", data=media_payload, timeout=15)
			resp.raise_for_status()
			media_type = "video" if is_video else "photo"
			logger.info("Sent %s with caption to Telegram.", media_type)
			return
		except Exception as exc:
			logger.error("Telegram send%s failed: %s", endpoint.replace("send", ""), exc)
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
