import os
import time
import logging
from typing import List, Dict, Optional
from urllib.parse import urlparse, urljoin, parse_qs, urlunparse, urlencode

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


GENERIC_GNEWS_DESC = "Comprehensive up-to-date news coverage"


class NewsFetcher:
	def __init__(self, query: str, locale: str = "ru", country: str = "RU", fallback_image_url: Optional[str] = None, feed_urls: Optional[List[str]] = None):
		self.query = query
		self.locale = locale
		self.country = country
		self.fallback_image_url = fallback_image_url
		self.feed_urls = [u.strip() for u in (feed_urls or []) if u and u.strip()]

	def fetch(self, max_items: int = 10, timeout_sec: int = 10) -> List[Dict[str, Optional[str]]]:
		# Используем только явные RSS фиды. Google News отключён.
		if not self.feed_urls:
			logger.warning("No RSS_FEEDS configured; Google News disabled; returning no items")
			return []
		feed_list = self.feed_urls
		results: List[Dict[str, Optional[str]]] = []
		per_feed_limit = max(3, max_items // max(1, len(feed_list)))
		headers = {
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
			"Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
			"Accept-Language": "en-US,en;q=0.9",
		}
		seen_links: set[str] = set()
		seen_titles: set[str] = set()
		for feed_url in feed_list:
			success = False
			for attempt in range(2):  # Try twice for RSS feeds
				try:
					resp = requests.get(feed_url, timeout=timeout_sec, headers=headers)
					resp.raise_for_status()
					success = True
					break
				except requests.exceptions.HTTPError as exc:
					if exc.response.status_code in [403, 503, 429] and attempt == 0:
						logger.info("RSS feed %s returned HTTP %s, retrying in 3s", feed_url, exc.response.status_code)
						time.sleep(3)
						continue
					logger.error("Failed to fetch RSS '%s': HTTP %s", feed_url, exc.response.status_code)
					break
				except Exception as exc:
					if attempt == 0:
						logger.info("RSS feed error for %s, retrying: %s", feed_url, exc)
						time.sleep(2)
						continue
					logger.error("Failed to fetch RSS '%s': %s", feed_url, exc)
					break
			
			if not success:
				continue

			soup = BeautifulSoup(resp.text, "xml")
			items = soup.find_all("entry") or soup.find_all("item")
			count = 0
			for item in items:
				if count >= per_feed_limit:
					break
				title_tag = item.find("title")
				link_tag = item.find("link")
				link_href = None
				if link_tag:
					# Atom: <link href="..."/>
					link_href = link_tag.get("href") or link_tag.text
				if not title_tag or not link_href:
					continue
				title = (title_tag.text or "").strip()
				raw_link = (link_href or "").strip()

				feed_desc_tag = item.find("summary") or item.find("description")
				feed_desc_text = None
				orig_from_desc = None
				if feed_desc_tag and feed_desc_tag.text:
					desc_html = feed_desc_tag.text
					desc_soup = BeautifulSoup(desc_html, "html.parser")
					for a in desc_soup.find_all("a", href=True):
						h = a["href"].strip()
						if h.startswith("http") and "news.google" not in urlparse(h).netloc:
							orig_from_desc = h
							break
					feed_desc_text = desc_soup.get_text(" ", strip=True)
					low = feed_desc_text.lower()
					if (
						"google news" in low
						or GENERIC_GNEWS_DESC.lower() in low
						or low.startswith("comprehensive up-to-date")
					):
						feed_desc_text = None

				# Определяем оригинальную ссылку
				orig_link = orig_from_desc
				if not orig_link:
					if "news.google.com" in urlparse(raw_link).netloc:
						orig_link = self._resolve_original_url(raw_link)
					else:
						orig_link = raw_link
				if not orig_link or urlparse(orig_link).netloc.endswith("news.google.com"):
					logger.info("Skipping item due to unresolved original URL: %s", raw_link)
					continue

				# Каноникализация и локальная дедупликация
				canon_link = self._canonicalize_url(orig_link)
				if canon_link in seen_links:
					continue
				seen_links.add(canon_link)
				title_key = self._title_key(title)
				if title_key in seen_titles:
					continue
				seen_titles.add(title_key)

				# Изображение/видео из RSS
				feed_image = None
				media_tag = item.find("media:content") or item.find("media:thumbnail")
				if media_tag and media_tag.get("url"):
					feed_image = media_tag.get("url")
				if not feed_image:
					enclosure = item.find("enclosure")
					if enclosure and enclosure.get("url"):
						media_type = (enclosure.get("type") or "").lower()
						# Accept images and videos
						if media_type.startswith("image") or media_type.startswith("video"):
							feed_image = enclosure.get("url")

				# Мета со страницы статьи (включая canonical)
				article_desc = None
				meta = self._get_article_meta(canon_link)
				# Если страница объявляет canonical — используем его для более устойчивой дедупликации
				if meta and meta.get("canonical_url"):
					cand = self._canonicalize_url(meta.get("canonical_url"))
					if cand and cand.startswith("http") and not urlparse(cand).netloc.endswith("news.google.com"):
						canon_link = cand
				meta_image = meta.get("image") if meta else None
				all_media = meta.get("all_media", []) if meta else []
				if meta and meta.get("description"):
					article_desc = meta.get("description")

				image_url = self._prefer_article_image(feed_image, meta_image)
				if not image_url and self.fallback_image_url:
					image_url = self.fallback_image_url

				results.append({
					"title": title,
					"link": canon_link,
					"image_url": image_url,
					"all_media": all_media,
					"description": article_desc or feed_desc_text,
				})
				count += 1
		return results

	def _prefer_article_image(self, feed_image: Optional[str], meta_image: Optional[str]) -> Optional[str]:
		if meta_image:
			if not feed_image:
				return meta_image
			feed_host = urlparse(feed_image).netloc
			if "news.google" in feed_host or "gstatic" in feed_host:
				return meta_image
		return feed_image or meta_image

	def _extract_external_from_gnews(self, soup: BeautifulSoup, base: str) -> Optional[str]:
		refresh = soup.find("meta", attrs={"http-equiv": "refresh"})
		if refresh and refresh.get("content"):
			content = refresh.get("content")
			if "url=" in content.lower():
				u = content.split("url=", 1)[-1].strip().strip("\"'")
				if u.startswith("http") and not urlparse(u).netloc.endswith("news.google.com"):
					return u
		amp = soup.find("link", attrs={"rel": "amphtml"})
		if amp and amp.get("href"):
			h = amp.get("href")
			if h.startswith("http") and not urlparse(h).netloc.endswith("news.google.com"):
				return h
		for a in soup.find_all("a", href=True):
			h = a["href"]
			if h.startswith("/url?") or h.startswith("https://www.google.com/url?"):
				try:
					qs = parse_qs(urlparse(h).query)
					candidate = (qs.get("url") or qs.get("q") or [None])[0]
					if candidate and urlparse(candidate).netloc and not urlparse(candidate).netloc.endswith("news.google.com"):
						return candidate
				except Exception:
					pass
			if h.startswith("http") and not urlparse(h).netloc.endswith("news.google.com"):
				return h
			abs_h = urljoin(base, h)
			if abs_h.startswith("http") and not urlparse(abs_h).netloc.endswith("news.google.com"):
				return abs_h
		return None

	def _resolve_original_url(self, link: str, timeout_sec: int = 10) -> Optional[str]:
		try:
			headers = {
				"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
				"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
				"Accept-Language": "en-US,en;q=0.9",
				"Referer": "https://news.google.com/",
			}
			resp = requests.get(link, timeout=timeout_sec, allow_redirects=True, headers=headers)
			final_url = resp.url
			host = urlparse(final_url).netloc
			if host and not host.endswith("news.google.com"):
				return self._canonicalize_url(final_url)
			soup = BeautifulSoup(resp.text, "html.parser")
			candidate = self._extract_external_from_gnews(soup, final_url)
			if candidate:
				return self._canonicalize_url(candidate)
		except Exception as exc:
			logger.info("Failed to resolve original URL: %s", exc)
		return None

	def _get_article_meta(self, page_url: str, timeout_sec: int = 10, max_retries: int = 2) -> Optional[Dict[str, Optional[str]]]:
		headers = {
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
			"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
			"Accept-Language": "en-US,en;q=0.9",
			"Cache-Control": "no-cache",
			"Pragma": "no-cache"
		}
		
		for attempt in range(max_retries + 1):
			try:
				resp = requests.get(page_url, timeout=timeout_sec, headers=headers, allow_redirects=True)
				resp.raise_for_status()
				break
			except requests.exceptions.HTTPError as exc:
				if exc.response.status_code in [403, 503, 429]:  # Common blocking/rate limit errors
					if attempt < max_retries:
						logger.info("HTTP %s for %s, retrying in %ds (attempt %d/%d)", 
								   exc.response.status_code, page_url, (attempt + 1) * 2, attempt + 1, max_retries + 1)
						time.sleep((attempt + 1) * 2)  # Exponential backoff
						continue
				logger.info("Could not fetch page for meta (HTTP %s): %s", exc.response.status_code, page_url)
				return None
			except Exception as exc:
				if attempt < max_retries:
					logger.info("Error fetching %s, retrying (attempt %d/%d): %s", page_url, attempt + 1, max_retries + 1, exc)
					time.sleep((attempt + 1))
					continue
				logger.info("Could not fetch page for meta after %d attempts: %s", max_retries + 1, exc)
				return None

		image = None
		all_media = []
		description = None
		canonical_url = None
		try:
			soup = BeautifulSoup(resp.text, "html.parser")
			host = urlparse(resp.url).netloc
			if host.endswith("news.google.com"):
				extra = self._extract_external_from_gnews(soup, resp.url)
				if extra:
					return self._get_article_meta(extra, timeout_sec=timeout_sec)

			# canonical URL (если есть) — влияет на дедупликацию
			canon_link = None
			try:
				# rel может быть списком; ищем тег, где есть 'canonical'
				for l in soup.find_all("link"):
					rel = l.get("rel")
					if rel and ("canonical" in rel or "Canonical" in rel):
						canon_link = l.get("href")
						break
			except Exception:
				canon_link = None
			if canon_link:
				canonical_url = self._canonicalize_url(canon_link)
				page_url = canonical_url or page_url

			# Collect all media from the page
			media_urls = set()
			
			# Meta tags for primary image/video
			for attrs in (
				{"property": "og:image:secure_url"},
				{"property": "og:image:url"},
				{"name": "twitter:image:src"},
				{"name": "twitter:image"},
				{"property": "og:image"},
				{"property": "og:video:secure_url"},
				{"property": "og:video:url"},
				{"property": "og:video"},
				{"name": "twitter:player:stream"},
				{"name": "twitter:player"},
			):
				meta = soup.find("meta", attrs=attrs)
				if meta and meta.get("content"):
					url = meta.get("content")
					if url:
						media_urls.add(url)
						if not image:  # Set first found as primary
							image = url
			
			# Link tags
			if not image:
				lnk = soup.find("link", attrs={"rel": "image_src"})
				if lnk and lnk.get("href"):
					url = lnk.get("href")
					image = url
					media_urls.add(url)
			
			# Find all img tags in article content
			for img in soup.find_all("img", src=True):
				src = img.get("src")
				if src and not src.startswith("data:"):
					# Convert relative URLs to absolute
					if src.startswith("//"):
						src = "https:" + src
					elif src.startswith("/"):
						src = urljoin(page_url, src)
					elif not src.startswith("http"):
						src = urljoin(page_url, src)
					
					# Filter out small icons and ads
					width = img.get("width")
					height = img.get("height")
					if width and height:
						try:
							w, h = int(width), int(height)
							if w < 100 or h < 100:  # Skip small images
								continue
						except ValueError:
							pass
					
					# Skip common ad/tracking pixels
					if any(skip in src.lower() for skip in ["pixel", "tracking", "analytics", "ads", "beacon"]):
						continue
					
					media_urls.add(src)
			
			# Find video tags
			for video in soup.find_all("video", src=True):
				src = video.get("src")
				if src:
					if src.startswith("//"):
						src = "https:" + src
					elif src.startswith("/"):
						src = urljoin(page_url, src)
					elif not src.startswith("http"):
						src = urljoin(page_url, src)
					media_urls.add(src)
			
			# Find video source tags
			for source in soup.find_all("source", src=True):
				src = source.get("src")
				if src:
					if src.startswith("//"):
						src = "https:" + src
					elif src.startswith("/"):
						src = urljoin(page_url, src)
					elif not src.startswith("http"):
						src = urljoin(page_url, src)
					media_urls.add(src)
			
			all_media = list(media_urls)

			for attrs in (
				{"property": "og:description"},
				{"name": "twitter:description"},
				{"name": "description"},
			):
				meta = soup.find("meta", attrs=attrs)
				if meta and meta.get("content"):
					description = meta.get("content").strip(); break
		except Exception as exc:
			logger.info("Failed parsing article meta: %s", exc)
		return {"image": image, "all_media": all_media, "description": description, "canonical_url": canonical_url or page_url}

	def _canonicalize_url(self, url: str) -> str:
		try:
			o = urlparse(url)
			# strip fragments
			o = o._replace(fragment="")
			# normalize host to lower
			host = o.netloc.lower()
			# remove common tracking params
			qs = parse_qs(o.query, keep_blank_values=False)
			blocked = {"utm_source","utm_medium","utm_campaign","utm_term","utm_content","utm_id","gclid","fbclid","mc_cid","mc_eid","igshid","ref","ref_src","ref_url","ncid","spm"}
			qs = {k:v for k,v in qs.items() if k not in blocked}
			# remove amp patterns
			path = o.path
			if path.endswith("/amp"):
				path = path[:-4]
			if "/amp/" in path:
				path = path.replace("/amp/", "/")
			# rebuild
			new_query = urlencode({k:v[0] if isinstance(v, list) and v else v for k,v in qs.items()}, doseq=False)
			o = o._replace(netloc=host, query=new_query, path=path)
			# drop trailing slash (except root)
			if o.path.endswith("/") and len(o.path) > 1:
				o = o._replace(path=o.path.rstrip("/"))
			return urlunparse(o)
		except Exception:
			return url

	def _title_key(self, title: str) -> str:
		s = title.lower().strip()
		reduced = []
		for ch in s:
			if ch.isalnum() or ch.isspace():
				reduced.append(ch)
		return " ".join("".join(reduced).split())
