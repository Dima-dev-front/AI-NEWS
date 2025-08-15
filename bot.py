import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Set, Tuple, Optional

from dotenv import load_dotenv

from news import NewsFetcher
from summarizer import Summarizer
from bot_utils import format_message_html, send_to_telegram, format_message_plain


logging.basicConfig(
	level=os.getenv("LOG_LEVEL", "INFO"),
	format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bot")


DATA_DIR = Path("data")
PUBLISHED_PATH = DATA_DIR / "published.json"
RECENT_TITLES_PATH = DATA_DIR / "recent_titles.json"


def ensure_storage() -> None:
	DATA_DIR.mkdir(parents=True, exist_ok=True)
	if not PUBLISHED_PATH.exists():
		PUBLISHED_PATH.write_text("[]", encoding="utf-8")
	if not RECENT_TITLES_PATH.exists():
		RECENT_TITLES_PATH.write_text("[]", encoding="utf-8")


def load_published() -> Set[str]:
	ensure_storage()
	try:
		data = json.loads(PUBLISHED_PATH.read_text(encoding="utf-8"))
		if isinstance(data, list):
			return set(map(str, data))
		return set()
	except Exception:
		return set()


def save_published(published: Set[str]) -> None:
	ensure_storage()
	PUBLISHED_PATH.write_text(json.dumps(sorted(list(published)), ensure_ascii=False, indent=2), encoding="utf-8")


def collapse_to_two_sentences(text: str, max_chars: int = 400) -> str:
	if not text:
		return ""
	text = text.strip()
	# Simple sentence split by . ! ?
	sentences = []
	tmp = ""
	for ch in text:
		tmp += ch
		if ch in ".!?":
			sentences.append(tmp.strip())
			tmp = ""
	if tmp.strip():
		sentences.append(tmp.strip())
	short = " ".join(sentences[:2]).strip()
	if not short:
		short = text
	if len(short) > max_chars:
		short = short[: max_chars - 3].rstrip() + "..."
	return short


def parse_feed_urls(env_value: str) -> list:
	if not env_value:
		return []
	return [u.strip() for u in env_value.split(",") if u.strip()]


def parse_ai_json(output: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
	if not output:
		return None, None, None
	text = output.strip()
	if text.startswith("```"):
		lines = text.splitlines()
		if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
			text = "\n".join(lines[1:-1]).strip()
	try:
		obj = json.loads(text)
		if isinstance(obj, dict):
			title = obj.get("title")
			summary = obj.get("summary")
			cta_url = obj.get("cta_url")
			if isinstance(title, str):
				title = title.strip()
			if isinstance(summary, str):
				summary = summary.strip()
			if isinstance(cta_url, str):
				cta_url = cta_url.strip()
			return (
				title if isinstance(title, str) and title else None,
				summary if isinstance(summary, str) and summary else None,
				cta_url if isinstance(cta_url, str) and cta_url.lower().startswith("http") else None,
			)
	except Exception:
		return None, None, None
	return None, None, None


def load_recent_titles() -> list:
	ensure_storage()
	try:
		data = json.loads(RECENT_TITLES_PATH.read_text(encoding="utf-8"))
		if isinstance(data, list):
			return [str(x) for x in data]
		return []
	except Exception:
		return []


def save_recent_titles(keys: list, max_size: int) -> None:
	# keep only the most recent max_size items
	trimmed = keys[-max_size:]
	RECENT_TITLES_PATH.write_text(json.dumps(trimmed, ensure_ascii=False, indent=2), encoding="utf-8")


def title_key(title: str) -> str:
	s = (title or "").lower().strip()
	reduced = []
	for ch in s:
		if ch.isalnum() or ch.isspace():
			reduced.append(ch)
	return " ".join("".join(reduced).split())


def main() -> None:
	load_dotenv()

	bot_token = os.getenv("TELEGRAM_TOKEN", "")
	chat_id = os.getenv("CHAT_ID", "")
	query = os.getenv("NEWS_QUERY", "Украина")
	model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
	fallback_image_url = os.getenv("FALLBACK_IMAGE_URL", "assets/ai-fallback.png")
	locale = os.getenv("LOCALE", "ru")
	country = os.getenv("COUNTRY", "RU")
	rss_feeds = parse_feed_urls(os.getenv("RSS_FEEDS", ""))
	run_once = os.getenv("RUN_ONCE", "").lower() in ("1", "true", "yes", "on")
	require_media = os.getenv("REQUIRE_MEDIA", "0").lower() in ("1", "true", "yes", "on")

	try:
		check_interval_min = int(os.getenv("CHECK_INTERVAL_MIN", "60"))
	except ValueError:
		check_interval_min = 60
	try:
		post_delay_sec = int(os.getenv("POST_DELAY_SEC", "60"))
	except ValueError:
		post_delay_sec = 60
	try:
		max_posts_per_cycle = int(os.getenv("MAX_POSTS_PER_CYCLE", "1"))
	except ValueError:
		max_posts_per_cycle = 1
	try:
		recent_titles_max = int(os.getenv("RECENT_TITLES_MAX", "300"))
	except ValueError:
		recent_titles_max = 300

	if not bot_token or not chat_id:
		logger.error("TELEGRAM_TOKEN and CHAT_ID must be set")
		sys.exit(1)

	if not rss_feeds:
		logger.error("RSS_FEEDS must be set (Google News is disabled)")
		sys.exit(1)

	fetcher = NewsFetcher(query=query, locale=locale, country=country, fallback_image_url=fallback_image_url, feed_urls=rss_feeds)
	summarizer = Summarizer(model_name=model_name)

	published_links = load_published()
	recent_title_keys = load_recent_titles()
	recent_title_keys_set = set(recent_title_keys)
	mode = "RSS_FEEDS"
	logger.info(
		"Starting bot. Mode=%s, Feeds=%d, Interval=%s min, Delay=%s sec, Published=%d",
		mode,
		len(rss_feeds),
		check_interval_min,
		post_delay_sec,
		len(published_links),
	)

	while True:
		try:
			items = fetcher.fetch(max_items=20)
			logger.info("Fetched %d items", len(items))

			# Позволяем ИИ выбрать самые интересные элементы (по заголовкам/ссылкам)
			candidate_view = [{"title": (it.get("title") or ""), "link": (it.get("link") or "")} for it in items]
			best_indices: list[int] = []
			try:
				best_indices = summarizer.select_best(candidate_view[:20]) or []
				logger.info("AI selected %d best items: %s", len(best_indices), best_indices)
			except Exception as exc:
				logger.warning("AI selection failed: %s", exc)
				best_indices = []
			# Построить порядок обхода: сначала предложенные ИИ, затем остальные
			seen_idx = set(int(i) for i in best_indices if isinstance(i, int) and 0 <= i < len(items))
			ordered_indices = list(seen_idx) + [i for i in range(len(items)) if i not in seen_idx]

			new_count = 0
			processed_count = 0
			skipped_reasons = {"duplicate_link": 0, "duplicate_title": 0, "no_media": 0, "ai_duplicate": 0}
			
			for idx in ordered_indices:
				item = items[idx]
				title = item.get("title") or ""
				link = item.get("link") or ""
				image_url = item.get("image_url") or None
				all_media = item.get("all_media", [])
				feed_or_meta_desc = item.get("description") or ""
				processed_count += 1
				
				if not title or not link:
					logger.debug("Skipping item %d: missing title or link", idx)
					continue

				if link in published_links:
					skipped_reasons["duplicate_link"] += 1
					logger.debug("Skipping item %d: already published - %s", idx, title[:50])
					continue

				# Early title-based dedupe on feed title
				orig_title_key = title_key(title)
				if orig_title_key and orig_title_key in recent_title_keys_set:
					skipped_reasons["duplicate_title"] += 1
					logger.debug("Skipping item %d: duplicate title - %s", idx, title[:50])
					continue

				ai_output = summarizer.summarize(title=title, url=link)
				parsed_title, parsed_summary, cta_url = parse_ai_json(ai_output)

				if parsed_summary:
					summary = parsed_summary
				else:
					# Local fallback summarization
					summary = collapse_to_two_sentences(feed_or_meta_desc)
					if not summary:
						# Last resort: just use title as a single-line summary
						summary = title

				# Prefer AI title if provided
				final_title = parsed_title.strip() if parsed_title else title

				# Dedupe with AI title if it differs
				ai_title_key = title_key(final_title)
				if ai_title_key and ai_title_key in recent_title_keys_set:
					skipped_reasons["ai_duplicate"] += 1
					logger.debug("Skipping item %d: AI title duplicate - %s", idx, final_title[:50])
					continue

				# Skip news without images or videos (if required)
				if require_media and not image_url:
					skipped_reasons["no_media"] += 1
					logger.debug("Skipping item %d: no media - %s", idx, final_title[:50])
					continue

				# Append CTA if present
				if cta_url:
					summary = f"{summary}\n\nСпробувати: {cta_url}"

				message_html = format_message_html(title=final_title, summary=summary, source_url=link)
				message_plain = format_message_plain(title=final_title, summary=summary, source_url=link)

				try:
					send_to_telegram(bot_token=bot_token, chat_id=chat_id, message_html=message_html, image_url=image_url, message_plain=message_plain, all_media=all_media, fallback_image_url=fallback_image_url)
					published_links.add(link)
					save_published(published_links)
					# Update recent titles store
					recent_title_keys.append(orig_title_key)
					if ai_title_key and ai_title_key != orig_title_key:
						recent_title_keys.append(ai_title_key)
					recent_title_keys_set = set(recent_title_keys)
					save_recent_titles(recent_title_keys, max_size=recent_titles_max)
					new_count += 1
					logger.info("Posted: %s", final_title)
				except Exception as exc:
					logger.error("Failed to post: %s", exc)

				if new_count >= max_posts_per_cycle:
					break

				time.sleep(post_delay_sec)

			# Log detailed statistics
			logger.info("Cycle complete: processed %d/%d items, posted %d, skipped: %s", 
					   processed_count, len(items), new_count, skipped_reasons)
			
			if new_count == 0:
				if processed_count == 0:
					logger.info("No items to process")
				else:
					logger.info("No new items to post - all %d items were filtered out", processed_count)
		except Exception as loop_exc:
			logger.error("Loop error: %s", loop_exc)

		# Exit immediately in one-shot mode
		if run_once:
			break

		time.sleep(max(1, check_interval_min) * 60)


if __name__ == "__main__":
	main()
