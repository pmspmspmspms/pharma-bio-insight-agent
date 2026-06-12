from __future__ import annotations

import json
import urllib.request
from datetime import datetime

from collectors import NewsItem
from config import Settings, TOPICS


def build_briefing_text(
    items_by_topic: dict[str, list[NewsItem]],
    settings: Settings,
    today: datetime,
    use_ai: bool,
) -> str:
    if use_ai and settings.openai_api_key:
        try:
            return _openai_summary(items_by_topic, settings, today)
        except Exception as exc:
            fallback = _fallback_summary(items_by_topic, today)
            return f"{fallback}\n\n> AI 요약 생성 실패: `{type(exc).__name__}`. 수집 결과 기반 요약으로 대체했습니다.\n"
    return _fallback_summary(items_by_topic, today)


def _openai_summary(
    items_by_topic: dict[str, list[NewsItem]],
    settings: Settings,
    today: datetime,
) -> str:
    payload = {
        "model": settings.openai_model,
        "input": _build_prompt(items_by_topic, today),
        "max_output_tokens": 2200,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
    text = _extract_response_text(data)
    if not text:
        raise RuntimeError("OpenAI response did not include text output")
    return text.strip()


def _build_prompt(items_by_topic: dict[str, list[NewsItem]], today: datetime) -> str:
    source_blocks: list[str] = []
    for topic_key, topic in TOPICS.items():
        topic_items = items_by_topic.get(topic_key, [])
        if not topic_items:
            source_blocks.append(f"## {topic['label']}\nNo collected sources.")
            continue
        source_blocks.append(f"## {topic['label']}")
        for index, item in enumerate(topic_items, start=1):
            source_blocks.append(
                "\n".join(
                    [
                        f"{index}. {item.title}",
                        f"   Source: {item.source}",
                        f"   Published: {item.published or 'unknown'}",
                        f"   Summary: {item.summary or 'no snippet'}",
                        f"   URL: {item.link}",
                    ]
                )
            )

    sources = "\n\n".join(source_blocks)
    return f"""
You are a pharma and biotech BD analyst for a Korean CRO/nonclinical testing business.
Write in Korean.

Date: {today.strftime('%Y-%m-%d')}

Create a concise daily briefing with these exact sections:
1. 오늘의 핵심 3줄
2. MFDS 규제·허가
3. 제약·바이오 BD 동향
4. in vitro ADME / DMPK / DDI
5. PGx / 약물유전자검사
6. Recombinant Enzymes / CYP / UGT
7. Market & Competitor Watch
8. Regulatory Watch
9. BD Opportunity Map
10. 고객 접근 멘트

Rules:
- Use only the collected source snippets below.
- For each topic, pick 3 to 5 useful items when available.
- If a topic has no collected sources, say so briefly and suggest what to watch next.
- Do not just summarize. Convert each item into business implications and actionable BD/PM insight.
- For important items, include market area, modality, pipeline stage, likely customer type, relevant SPMED service, BD Opportunity Score from 1 to 5, and recommended next action.
- Watch for therapeutic areas such as oncology, CNS, metabolic disease, rare disease, infection, and cell/gene therapy.
- Watch for modalities such as ADC, PROTAC, RNA therapeutics, cell and gene therapy, radiopharmaceuticals, bispecific antibodies, AI drug discovery, NAMs/organoid, DMPK/PBPK/MIDD, companion diagnostics, and PGx.
- Keep the tone practical for BD, PM, customer lead generation, CRO services, and Korean pharma/biotech monitoring.
- Include source links inline.
- Do not invent facts that are not supported by the snippets.

Collected sources:

{sources}
""".strip()


def _extract_response_text(data: dict) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    parts: list[str] = []
    for output in data.get("output", []):
        for content in output.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(content["text"])
    return "\n".join(parts)


def _fallback_summary(items_by_topic: dict[str, list[NewsItem]], today: datetime) -> str:
    lines = [
        f"# 제약·바이오 데일리 인사이트 ({today.strftime('%Y-%m-%d')})",
        "",
        "AI 요약 없이 수집 결과를 주제별로 정리했습니다.",
        "",
        "## 오늘의 핵심 요약",
        "",
        "- 주요 뉴스와 공식 자료를 MFDS 규제·허가, 제약·바이오 BD 동향, ADME, PGx, 효소 서비스 관점으로 나눠 확인하세요.",
        "- 고객 접점에서는 허가·규제 변화, 기술수출, 파트너링, 투자, 임상 진입, 규제 제출, 약물상호작용, 바이오마커, 효소 기반 시험 수요를 연결해보면 좋습니다.",
        "",
    ]
    for topic_key, topic in TOPICS.items():
        topic_items = items_by_topic.get(topic_key, [])
        lines.extend([f"## {topic['label']}", ""])
        if not topic_items:
            lines.extend(
                [
                    "- 최근 설정 기간 안에서 수집된 항목이 없습니다.",
                    "- 검색어를 좁히거나 `BRIEFING_DAYS_BACK` 값을 늘리면 더 많은 자료를 볼 수 있습니다.",
                    "",
                ]
            )
            continue
        for item in topic_items[:5]:
            summary = f" — {item.summary}" if item.summary else ""
            lines.append(f"- [{item.title}]({item.link}) ({item.source}){summary}")
        lines.append("")
    lines.extend(
        [
            "## BD 활용 포인트",
            "",
            "- 식약처 보도자료, 행정예고, 민원인안내서, 안전성 서한은 고객에게 연락할 가장 자연스러운 명분입니다.",
            "- 제약·바이오 BD 동향은 기술수출, 투자 유치, 공동개발, 임상 진입, CDMO/CRO 협력 신호를 함께 확인하세요.",
            "- ADME/DDI 자료는 초기 개발 패키지와 규제 제출 리스크를 낮추는 대화 소재로 쓰기 좋습니다.",
            "- PGx와 바이오마커 뉴스는 동반진단, 환자 선별, 라벨 업데이트와 연결해 접근하세요.",
            "- CYP·UGT 효소 관련 자료는 reaction phenotyping, enzyme inhibition, non-CYP metabolism 수요 발굴에 활용하세요.",
            "",
            "## BD Opportunity Map",
            "",
            "- Score 5: 바로 컨택 후보. 기술이전, IND, 허가, 규제 변화와 직접 연결된 자료입니다.",
            "- Score 4: 영업 소재 가능. 고객군과 제안 서비스가 명확한 자료입니다.",
            "- Score 3: 추후 연락 후보. 후속 뉴스나 추가 자료 확인 후 접근하세요.",
            "- 대시보드 카드의 시장, 단계, 고객군, SPMED 서비스, 액션 항목을 함께 확인하세요.",
        ]
    )
    return "\n".join(lines)
