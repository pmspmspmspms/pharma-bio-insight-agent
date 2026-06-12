from __future__ import annotations

import email.utils
import difflib
import html
import json
import re
import ssl
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from config import MFDS_RSS_FEEDS, Settings, TOPICS


MAX_ITEMS_PER_ENTITY_PER_TOPIC = 2

EXCLUDED_STORY_KEYWORDS = [
    "채용",
    "공채",
    "수시채용",
    "채용공고",
    "채용설명회",
    "구인",
    "구직",
    "취업",
    "인턴",
    "신입사원",
    "경력직",
    "인재 모집",
    "인재모집",
    "영입",
    "선임",
    "임명",
    "인사",
    "승진",
    "hiring",
    "recruit",
    "recruitment",
    "job opening",
    "job posting",
    "careers",
    "appointed",
    "appointment",
]


@dataclass(frozen=True)
class NewsItem:
    topic_key: str
    topic_label: str
    title: str
    link: str
    source: str
    published: str
    summary: str


def collect_all(settings: Settings, today: datetime) -> dict[str, list[NewsItem]]:
    collected: dict[str, list[NewsItem]] = {}
    for topic_key, topic in TOPICS.items():
        items: list[NewsItem] = []
        if topic_key == "mfds_regulatory":
            items.extend(_collect_mfds(topic_key, topic["label"], settings, today))
        for query in topic["queries"]:
            items.extend(_collect_google_news(topic_key, topic["label"], query, settings, today))
            if settings.naver_client_id and settings.naver_client_secret:
                items.extend(_collect_naver_news(topic_key, topic["label"], query, settings))
        collected[topic_key] = _dedupe(items)[: settings.max_items_per_topic]
    return collected


def _collect_mfds(
    topic_key: str,
    topic_label: str,
    settings: Settings,
    today: datetime,
) -> list[NewsItem]:
    cutoff = today - timedelta(days=settings.days_back)
    items: list[NewsItem] = []
    for feed in MFDS_RSS_FEEDS:
        try:
            xml_text = _fetch_text(feed["url"])
            feed_items = _parse_rss(xml_text, topic_key, topic_label, feed["label"])
        except Exception:
            continue
        for item in feed_items:
            if _is_recent(item.published, cutoff):
                items.append(item)
    return items


def _collect_google_news(
    topic_key: str,
    topic_label: str,
    query: str,
    settings: Settings,
    today: datetime,
) -> list[NewsItem]:
    query_with_window = f"{query} when:{settings.days_back}d"
    locale = _google_news_locale(query)
    url = (
        "https://news.google.com/rss/search?"
        + urllib.parse.urlencode(
            {
                "q": query_with_window,
                "hl": locale["hl"],
                "gl": locale["gl"],
                "ceid": locale["ceid"],
            }
        )
    )
    try:
        xml_text = _fetch_text(url)
    except Exception:
        return []
    cutoff = today - timedelta(days=settings.days_back)
    return [
        item
        for item in _parse_rss(xml_text, topic_key, topic_label, "Google News")
        if _is_recent(item.published, cutoff)
    ]


def _collect_naver_news(
    topic_key: str,
    topic_label: str,
    query: str,
    settings: Settings,
) -> list[NewsItem]:
    url = "https://openapi.naver.com/v1/search/news.json?" + urllib.parse.urlencode(
        {"query": query, "display": settings.max_items_per_topic, "sort": "date"}
    )
    headers = {
        "X-Naver-Client-Id": settings.naver_client_id or "",
        "X-Naver-Client-Secret": settings.naver_client_secret or "",
    }
    try:
        payload = json.loads(_fetch_text(url, headers=headers))
    except Exception:
        return []

    items: list[NewsItem] = []
    for raw in payload.get("items", []):
        items.append(
            NewsItem(
                topic_key=topic_key,
                topic_label=topic_label,
                title=_clean(raw.get("title", "")),
                link=raw.get("originallink") or raw.get("link") or "",
                source="Naver News",
                published=raw.get("pubDate", ""),
                summary=_clean(raw.get("description", "")),
            )
        )
    return items


def _parse_rss(xml_text: str, topic_key: str, topic_label: str, source: str) -> list[NewsItem]:
    root = ET.fromstring(xml_text)
    items: list[NewsItem] = []
    for node in root.findall(".//item"):
        title = _node_text(node, "title")
        link = _node_text(node, "link")
        published = _node_text(node, "pubDate")
        summary = _node_text(node, "description")
        source_name = _node_text(node, "source") or source
        if title and link:
            items.append(
                NewsItem(
                    topic_key=topic_key,
                    topic_label=topic_label,
                    title=_clean(title),
                    link=link.strip(),
                    source=_clean(source_name),
                    published=published.strip(),
                    summary=_clean(summary),
                )
            )
    return items


def _google_news_locale(query: str) -> dict[str, str]:
    if any("\uac00" <= char <= "\ud7a3" for char in query):
        return {"hl": "ko", "gl": "KR", "ceid": "KR:ko"}
    return {"hl": "en-US", "gl": "US", "ceid": "US:en"}


def _fetch_text(url: str, headers: dict[str, str] | None = None) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "pharma-bio-insight-agent/0.1",
            **(headers or {}),
        },
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=25, context=context) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, "replace")


def _dedupe(items: Iterable[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    story_titles: list[str] = []
    entity_counts: dict[str, int] = {}
    deduped: list[NewsItem] = []
    for item in items:
        if _is_excluded_story(item):
            continue
        key = _normalize_url(item.link) or item.title.lower()
        if key in seen:
            continue
        story_title = _normalize_story_title(item.title)
        if story_title and any(_is_same_story(story_title, existing) for existing in story_titles):
            continue
        entity = _primary_entity(story_title)
        if entity and entity_counts.get(entity, 0) >= MAX_ITEMS_PER_ENTITY_PER_TOPIC:
            continue
        seen.add(key)
        if story_title:
            story_titles.append(story_title)
        if entity:
            entity_counts[entity] = entity_counts.get(entity, 0) + 1
        deduped.append(item)
    return deduped


def _is_excluded_story(item: NewsItem) -> bool:
    text = _normalize_story_title(f"{item.title} {item.summary}")
    return any(keyword in text for keyword in EXCLUDED_STORY_KEYWORDS)


def _normalize_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(k, v) for k, v in query if not k.lower().startswith("utm_")]
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def _normalize_story_title(title: str) -> str:
    text = unicodedata.normalize("NFKC", title or "").lower()
    text = re.split(r"\s+-\s+", text, maxsplit=1)[0]
    text = re.sub(r"일라이\s*릴리[에와]?", "릴리", text)
    text = re.sub(r"일라이릴리[에와]?", "릴리", text)
    text = re.sub(r"릴리[에와]", "릴리", text)
    text = text.replace("한미약품그룹", "한미약품")
    text = text.replace("기술 수출", "기술수출")
    text = re.sub(r"(?<=\d)\.(?=\d)", "", text)
    text = re.sub(r"(\d+)조원", r"\1조", text)
    text = re.sub(r"[^\w가-힣]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _is_same_story(a: str, b: str) -> bool:
    if a == b:
        return True

    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    if ratio >= 0.72:
        return True

    tokens_a = _story_tokens(a)
    tokens_b = _story_tokens(b)
    if not tokens_a or not tokens_b:
        return False

    shared = tokens_a & tokens_b
    union = tokens_a | tokens_b
    jaccard = len(shared) / len(union)
    has_event_marker = any(_is_event_marker(token) for token in shared)

    if jaccard >= 0.46 and ratio >= 0.52:
        return True
    if len(shared) >= 3 and has_event_marker and ratio >= 0.48:
        return True
    return False


def _story_tokens(title: str) -> set[str]:
    stopwords = {
        "뉴스",
        "단독",
        "종합",
        "속보",
        "보도",
        "자료",
        "규모",
        "최대",
        "관련",
        "시장",
        "개발",
        "신약",
        "제약",
        "바이오",
        "pharma",
        "biotech",
        "news",
    }
    return {token for token in title.split() if len(token) >= 2 and token not in stopwords}


def _primary_entity(title: str) -> str | None:
    alias_map = {
        "한미": "한미약품",
        "한미약품": "한미약품",
        "넥스트앤바이오": "넥스트앤바이오",
        "에스피메드": "에스피메드",
    }
    for alias, canonical in alias_map.items():
        if alias in title:
            return canonical

    for token in title.split():
        if token.endswith(("약품", "제약", "바이오", "헬스케어", "랩스")):
            return token
        if token in {"bioivt", "nature"}:
            return token
    return None


def _is_event_marker(token: str) -> bool:
    markers = {
        "기술수출",
        "기술이전",
        "투자",
        "투자유치",
        "수출",
        "계약",
        "승인",
        "허가",
        "임상",
        "파트너링",
        "공동개발",
        "ipo",
        "m&a",
        "mou",
        "deal",
        "approval",
        "license",
        "licensing",
        "collaboration",
        "partnership",
    }
    return token in markers or any(char.isdigit() for char in token)


def _is_recent(published: str, cutoff: datetime) -> bool:
    if not published:
        return True
    try:
        parsed = email.utils.parsedate_to_datetime(published)
    except Exception:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed >= cutoff


def _node_text(node: ET.Element, name: str) -> str:
    child = node.find(name)
    return child.text if child is not None and child.text else ""


def _clean(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()
