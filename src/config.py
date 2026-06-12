from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: str | Path) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


TOPICS = {
    "mfds_regulatory": {
        "label": "MFDS 규제·허가",
        "queries": [],
    },
    "new_drug": {
        "label": "제약·바이오 BD 동향",
        "queries": [
            "제약 바이오 기술수출 투자 임상",
            "제약바이오 파트너링 M&A 기술이전",
            "바이오 IPO 투자 유치 공동개발",
            "Korea pharma biotech licensing partnership investment",
            "pharma biotech business development licensing M&A partnership",
            "biotech funding IPO partnership clinical trial",
            "CDMO CRO biotech partnership Korea",
        ],
    },
    "in_vitro_adme": {
        "label": "in vitro ADME",
        "queries": [
            "in vitro ADME",
            "DMPK ADME",
            "drug interaction DDI guidance",
            "비임상 ADME DMPK",
        ],
    },
    "pgx": {
        "label": "PGx / 약물유전자검사",
        "queries": [
            "pharmacogenomics PGx",
            "pharmacogenomic biomarker FDA",
            "약물유전체 약물유전자검사",
            "companion diagnostic biomarker",
        ],
    },
    "recombinant_enzymes": {
        "label": "Recombinant Enzymes / CYP·UGT 효소",
        "queries": [
            "recombinant CYP enzyme",
            "UGT enzyme assay",
            "CYP450 reaction phenotyping",
            "약물대사효소 CYP UGT",
        ],
    },
}


MFDS_RSS_FEEDS = [
    {
        "label": "식약처 보도자료",
        "url": "http://www.mfds.go.kr/www/rss/brd.do?brdId=ntc0021",
    },
    {
        "label": "식약처 행정예고",
        "url": "http://www.mfds.go.kr/www/rss/brd.do?brdId=data0009",
    },
    {
        "label": "식약처 안전성 서한",
        "url": "http://www.mfds.go.kr/www/rss/brd.do?brdId=seohan001",
    },
    {
        "label": "식약처 민원인안내서",
        "url": "http://www.mfds.go.kr/www/rss/brd.do?brdId=data0011",
    },
    {
        "label": "식약처 안내서/지침",
        "url": "http://www.mfds.go.kr/www/rss/brd.do?brdId=data0013",
    },
    {
        "label": "식약처 최근 개정 법령",
        "url": "http://www.mfds.go.kr/www/rss/brd.do?brdId=data0008",
    },
    {
        "label": "식약처 의약품·의약외품 행정처분",
        "url": "http://www.mfds.go.kr/www/rss/brd.do?brdId=plc0117",
    },
    {
        "label": "식약처 바이오 행정처분",
        "url": "http://www.mfds.go.kr/www/rss/brd.do?brdId=plc0138",
    },
]


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_model: str
    naver_client_id: str | None
    naver_client_secret: str | None
    slack_webhook_url: str | None
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    email_from: str | None
    email_to: str | None
    timezone: str
    days_back: int
    max_items_per_topic: int
    output_dir: Path
    database_path: Path


def _optional(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _path_from_env(name: str, default: Path, project_root: Path) -> Path:
    raw = os.getenv(name, "").strip()
    path = Path(raw) if raw else default
    return path if path.is_absolute() else project_root / path


def load_settings(output_dir: str | None = None, database_path: str | None = None) -> Settings:
    project_root = Path(__file__).resolve().parents[1]
    candidates = [
        project_root / "local.env",
        project_root / ".env",
        project_root / "env.txt",
        Path("local.env"),
        Path(".env"),
        Path("env.txt"),
    ]
    seen: set[Path] = set()
    for env_file in candidates:
        env_path = env_file.resolve()
        if env_path in seen:
            continue
        seen.add(env_path)
        load_dotenv(env_path)
    return Settings(
        openai_api_key=_optional("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini").strip() or "gpt-5-mini",
        naver_client_id=_optional("NAVER_CLIENT_ID"),
        naver_client_secret=_optional("NAVER_CLIENT_SECRET"),
        slack_webhook_url=_optional("SLACK_WEBHOOK_URL"),
        smtp_host=_optional("SMTP_HOST"),
        smtp_port=_int_env("SMTP_PORT", 587),
        smtp_username=_optional("SMTP_USERNAME"),
        smtp_password=_optional("SMTP_PASSWORD"),
        email_from=_optional("EMAIL_FROM"),
        email_to=_optional("EMAIL_TO"),
        timezone=os.getenv("BRIEFING_TIMEZONE", "Asia/Seoul").strip() or "Asia/Seoul",
        days_back=_int_env("BRIEFING_DAYS_BACK", 14),
        max_items_per_topic=_int_env("MAX_ITEMS_PER_TOPIC", 8),
        output_dir=Path(output_dir or os.getenv("BRIEFING_OUTPUT_DIR", "briefings")),
        database_path=Path(database_path)
        if database_path
        else _path_from_env("BRIEFING_DB_PATH", Path("data") / "insights.sqlite", project_root),
    )
