import logging
import os
from typing import Optional


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
					'нарешті', 'врешті', 'загалом', 'взагалі', 'справді', 'насправді',
					'звичайно', 'безумовно', 'можливо', 'ймовірно', 'здається',
					'😄', '😅', '🤔', '🙃', '😏', '🤷', '💭', '🎯'
				]) or
				# Short witty sentence patterns (increased threshold)
				len(sentence.split()) <= 15 or
				# Always treat last sentence as comment if it's short enough
				(is_last and len(sentence.split()) <= 10)
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
	Select appropriate icon based on text content with variety and randomization
	"""
	text_lower = text.lower()
	
	# Technology/AI related - multiple options
	if any(word in text_lower for word in ['штучний інтелект', 'ай', 'ші', 'технологі', 'алгоритм', 'робот', 'автоматизаці', 'нейрон', 'машинн', 'код', 'програм', 'цифров', 'данн', 'обчислен']):
		tech_icons = ['🤖', '⚡', '🔬', '💻', '🧠', '⚙️']
		return _select_varied_icon(tech_icons, text_lower)
	
	# Money/business related - multiple options
	if any(word in text_lower for word in ['гроші', 'долар', 'інвестиці', 'прибуток', 'бізнес', 'компані', 'стартап', 'фінанс', 'капітал', 'ринок']):
		money_icons = ['💰', '💸', '📈', '🏦', '💎', '🤑']
		return _select_varied_icon(money_icons, text_lower)
	
	# Surprise/shock/unexpected - multiple options
	if any(word in text_lower for word in ['несподівано', 'шокуюч', 'вражаюч', 'дивно', 'неймовірно', 'вау', 'ого', 'ничего себе']):
		surprise_icons = ['😲', '🤯', '😱', '🙀', '😮', '🤨']
		return _select_varied_icon(surprise_icons, text_lower)
	
	# Positive/success/celebration - multiple options
	if any(word in text_lower for word in ['чудово', 'відмінно', 'успішно', 'перемог', 'досягнення', 'круто', 'супер', 'класно']):
		positive_icons = ['🎉', '🚀', '✨', '🔥', '👏', '🥳', '🌟']
		return _select_varied_icon(positive_icons, text_lower)
	
	# Negative/concern/warning - multiple options
	if any(word in text_lower for word in ['проблем', 'загроз', 'небезпек', 'кризи', 'жахлив', 'погано', 'провал']):
		negative_icons = ['⚠️', '🚨', '😬', '😰', '🤦', '💀']
		return _select_varied_icon(negative_icons, text_lower)
	
	# Thinking/analysis/research - multiple options
	if any(word in text_lower for word in ['думк', 'аналіз', 'дослідженн', 'вивчен', 'з\'ясуван', 'розбир', 'вивчен']):
		thinking_icons = ['🤔', '🧐', '💡', '📊', '🔍', '📝']
		return _select_varied_icon(thinking_icons, text_lower)
	
	# Fun/entertainment/humor - multiple options
	if any(word in text_lower for word in ['смішно', 'весело', 'кумедно', 'жарт', 'гумор', 'прикол', 'ржач', 'кумедн', 'забавн']):
		fun_icons = ['😄', '😂', '🤣', '😆', '🙃', '😜', '🤪']
		return _select_varied_icon(fun_icons, text_lower)
	
	# Sarcasm/irony patterns - expanded
	if any(pattern in text_lower for pattern in ['звісно', 'ага', 'ну да', 'конечно', 'ясно', 'логично', 'звичайно', 'як завжди', 'типово', 'класично']):
		sarcasm_icons = ['🙄', '😏', '🤨', '😑', '🤷', '🙃']
		return _select_varied_icon(sarcasm_icons, text_lower)
	
	# Question/doubt patterns
	if any(pattern in text_lower for pattern in ['невідомо', 'хто знає', 'цікаво', 'питання', 'загадка', 'незрозуміло']):
		question_icons = ['🤷', '❓', '🤔', '🧐', '😕', '🤨']
		return _select_varied_icon(question_icons, text_lower)
	
	# Time/speed related
	if any(word in text_lower for word in ['швидко', 'повільно', 'час', 'терміново', 'негайно']):
		time_icons = ['⏰', '⚡', '🐌', '⏳', '🏃', '🕐']
		return _select_varied_icon(time_icons, text_lower)
	
	# Default varied icons for general comments
	default_icons = ['💭', '🎯', '📌', '💡', '🤷', '😌', '🎪', '🎲']
	return _select_varied_icon(default_icons, text_lower)


def _select_varied_icon(icons: list, text: str) -> str:
	"""
	Select icon with pseudo-randomization based on text content for variety
	"""
	# Use text hash for consistent but varied selection
	text_hash = hash(text) % len(icons)
	return icons[text_hash]


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


def escape_html(text: str) -> str:
	return (
		text.replace("&", "&amp;")
		.replace("<", "&lt;")
		.replace(">", "&gt;")
		.replace('"', "&quot;")
	)


def send_to_telegram(bot_token: str, chat_id: str, message_html: str, image_url: Optional[str] = None, message_plain: Optional[str] = None, all_media: Optional[list] = None, fallback_image_url: Optional[str] = None) -> None:
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
	
	# Use best_media_url if found, otherwise fallback to image_url, then to fallback_image_url
	final_media_url = best_media_url or image_url or fallback_image_url

	# Send media with caption if available
	if final_media_url:
		caption = message_html
		if len(caption) > 1024:
			caption = caption[:1021] + "..."
		
		# Determine if it's a video or photo
		lower_url = final_media_url.lower()
		is_video = any(ext in lower_url for ext in ['.mp4', '.mov', '.avi', '.webm', '.mkv'])
		is_local_file = not final_media_url.startswith('http')
		
		# Check if caption contains CTA links and disable preview
		disable_preview = "Спробувати:" in caption or "Попробовать:" in caption or "Try:" in caption
		
		if is_local_file and os.path.exists(final_media_url):
			# Send local file
			try:
				with open(final_media_url, 'rb') as file:
					files = {'photo': file} if not is_video else {'video': file}
					data = {
						"chat_id": chat_id,
						"caption": caption,
						"parse_mode": "HTML",
					}
					if disable_preview:
						data["disable_web_page_preview"] = True
					
					endpoint = "sendPhoto" if not is_video else "sendVideo"
					resp = requests.post(f"{base_url}/{endpoint}", data=data, files=files, timeout=30)
					resp.raise_for_status()
					media_type = "photo" if not is_video else "video"
					logger.info("Sent local %s with caption to Telegram.", media_type)
					return
			except Exception as exc:
				logger.error("Failed to send local file %s: %s", final_media_url, exc)
				# Fall through to URL method or text-only
		
		# Send URL-based media
		media_payload = {
			"chat_id": chat_id,
			"caption": caption,
			"parse_mode": "HTML",
		}
		
		if disable_preview:
			media_payload["disable_web_page_preview"] = True
		
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
	# Check if message contains CTA links and disable preview for them
	disable_preview = "Спробувати:" in message_html or "Попробовать:" in message_html or "Try:" in message_html
	
	payload_html = {
		"chat_id": chat_id,
		"text": message_html,
		"parse_mode": "HTML",
		"disable_web_page_preview": disable_preview,
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
