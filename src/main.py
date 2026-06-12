from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from collectors import collect_all
from config import load_settings
from dashboard import render_dashboard
from db import save_run
from delivery import deliver
from summarizer import build_briefing_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a daily pharma and biotech BD briefing.")
    parser.add_argument("--no-ai", action="store_true", help="Skip OpenAI summary even if OPENAI_API_KEY is set.")
    parser.add_argument("--output-dir", default=None, help="Directory for generated Markdown briefings.")
    parser.add_argument("--db-path", default=None, help="SQLite database path for accumulated insight history.")
    parser.add_argument("--date", default=None, help="Override briefing date as YYYY-MM-DD.")
    args = parser.parse_args()

    settings = load_settings(args.output_dir, args.db_path)
    today = _today(settings.timezone, args.date)
    items_by_topic = collect_all(settings, today)
    item_count = sum(len(items) for items in items_by_topic.values())
    if item_count == 0:
        raise RuntimeError(
            "No items were collected. Network access may be blocked, so existing briefing/dashboard files were not overwritten."
        )
    markdown = build_briefing_text(items_by_topic, settings, today, use_ai=not args.no_ai)

    settings.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = settings.output_dir / f"pharma-bio-briefing-{today.strftime('%Y-%m-%d')}.md"
    output_path.write_text(markdown + "\n", encoding="utf-8")
    expected_dashboard_path = settings.output_dir / "dashboard" / "index.html"
    db_stats = save_run(items_by_topic, settings, today, output_path, expected_dashboard_path)
    dashboard_path = render_dashboard(items_by_topic, markdown, today, settings.output_dir, db_stats)

    title = f"제약·바이오 데일리 인사이트 {today.strftime('%Y-%m-%d')}"
    delivered = deliver(title, markdown, settings)
    delivery_text = ", ".join(delivered) if delivered else "no external delivery configured"
    print(f"Wrote {Path(output_path).resolve()}")
    print(f"Dashboard {Path(dashboard_path).resolve()}")
    print(f"Database {db_stats['path']} ({db_stats['totalArticles']} articles, {db_stats['totalRuns']} runs)")
    print(f"Delivery: {delivery_text}")


def _today(timezone_name: str, date_override: str | None) -> datetime:
    if date_override:
        return datetime.strptime(date_override, "%Y-%m-%d")
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz)


if __name__ == "__main__":
    main()
