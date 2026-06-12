from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from collectors import NewsItem
from config import TOPICS


def render_dashboard(
    items_by_topic: dict[str, list[NewsItem]],
    markdown: str,
    today: datetime,
    output_dir: Path,
    database_summary: dict | None = None,
) -> Path:
    dashboard_dir = output_dir / "dashboard"
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    dashboard_path = dashboard_dir / "index.html"
    data = _build_dashboard_data(items_by_topic, markdown, today, database_summary)
    dashboard_path.write_text(_html(data), encoding="utf-8")
    return dashboard_path


def _build_dashboard_data(
    items_by_topic: dict[str, list[NewsItem]],
    markdown: str,
    today: datetime,
    database_summary: dict | None = None,
) -> dict:
    topics = []
    all_items = []
    for topic_key, topic in TOPICS.items():
        topic_items = []
        for raw_item in items_by_topic.get(topic_key, []):
            item = _item_to_dashboard(raw_item)
            topic_items.append(item)
            all_items.append(item)
        topics.append(
            {
                "key": topic_key,
                "label": topic["label"],
                "count": len(topic_items),
                "items": topic_items,
            }
        )

    high_priority = [item for item in all_items if item["opportunityScore"] >= 4]
    regulatory = [
        item
        for item in all_items
        if item["signal"] == "Regulatory" or _contains(item, ["fda", "mfds", "식약처", "허가", "guidance"])
    ]
    signals = {}
    for item in all_items:
        signals[item["signal"]] = signals.get(item["signal"], 0) + 1

    return {
        "date": today.strftime("%Y-%m-%d"),
        "generatedLabel": today.strftime("%Y.%m.%d"),
        "topics": topics,
        "items": all_items,
        "actions": _build_actions(high_priority, topics),
        "metrics": {
            "totalItems": len(all_items),
            "highPriority": len(high_priority),
            "regulatory": len(regulatory),
            "activeTopics": sum(1 for topic in topics if topic["count"] > 0),
        },
        "signals": signals,
        "summary": _extract_summary(markdown),
        "database": database_summary or {},
    }


def _item_to_dashboard(item: NewsItem) -> dict:
    text = f"{item.title} {item.summary} {item.source}".lower()
    signal = _signal(text)
    market_area = _market_area(text)
    modality = _modality(text)
    pipeline_stage = _pipeline_stage(text)
    customer_type = _customer_type(text, signal)
    service = _spmed_service(text, signal)
    score = _opportunity_score(text, signal, pipeline_stage)
    return {
        "topicKey": item.topic_key,
        "topicLabel": item.topic_label,
        "title": item.title,
        "source": item.source or "Source",
        "published": item.published or "unknown",
        "summary": item.summary or "",
        "link": item.link,
        "signal": signal,
        "priority": "high" if score >= 4 else "medium",
        "angle": _commercial_angle(signal),
        "marketArea": market_area,
        "marketStage": _market_stage(text, signal),
        "modality": modality,
        "pipelineStage": pipeline_stage,
        "customerType": customer_type,
        "service": service,
        "opportunityScore": score,
        "nextAction": _next_action(score, service),
        "riskNote": _risk_note(signal),
    }


def _signal(text: str) -> str:
    if _has(
        text,
        [
            "기술수출",
            "기술이전",
            "투자",
            "투자유치",
            "m&a",
            "ipo",
            "공동개발",
            "파트너링",
            "license",
            "licensing",
            "collaboration",
            "deal",
            "partner",
            "funding",
            "investment",
        ],
    ):
        return "Deal"
    if _has(text, ["fda", "mfds", "식약처", "guidance", "승인", "허가", "regulatory", "approval"]):
        return "Regulatory"
    if _has(text, ["adme", "dmpk", "ddi", "cyp", "ugt", "transporter", "phenotyping"]):
        return "Assay"
    if _has(text, ["pgx", "pharmacogen", "biomarker", "동반진단", "약물유전체"]):
        return "Precision"
    return "Market"


def _priority(text: str, signal: str) -> str:
    high_markers = [
        "기술수출",
        "fda",
        "mfds",
        "승인",
        "허가",
        "phase",
        "임상",
        "guidance",
        "licensing",
        "collaboration",
        "deal",
        "biomarker",
    ]
    if signal in {"Deal", "Regulatory"} or _has(text, high_markers):
        return "high"
    return "medium"


def _commercial_angle(signal: str) -> str:
    angles = {
        "Deal": "기술이전·투자·공동개발 전 자료 패키지 보강",
        "Regulatory": "허가·규제 제출 리스크 점검",
        "Assay": "ADME/DDI·효소 시험 수요 발굴",
        "Precision": "바이오마커·환자 선별 전략 연결",
        "Market": "시장 변화와 고객 접점 후보 추적",
    }
    return angles.get(signal, angles["Market"])


def _market_area(text: str) -> str:
    if _has(text, ["oncology", "cancer", "tumor", "항암", "암", "adc"]):
        return "항암"
    if _has(text, ["cns", "neuro", "alzheimer", "parkinson", "우울증", "치매", "중추신경"]):
        return "CNS"
    if _has(text, ["obesity", "diabetes", "glp", "대사", "비만", "당뇨"]):
        return "대사질환"
    if _has(text, ["rare", "orphan", "희귀"]):
        return "희귀질환"
    if _has(text, ["infection", "vaccine", "antiviral", "감염", "백신"]):
        return "감염병"
    if _has(text, ["cell therapy", "gene therapy", "세포치료", "유전자치료"]):
        return "세포·유전자치료"
    return "제약·바이오"


def _market_stage(text: str, signal: str) -> str:
    if signal == "Regulatory" or _has(text, ["guidance", "가이드라인", "행정예고", "규제"]):
        return "규제 변화"
    if _has(text, ["patent cliff", "경쟁", "제네릭", "biosimilar", "바이오시밀러"]):
        return "경쟁 심화"
    if _has(text, ["growth", "성장", "투자", "funding", "ipo", "반등"]):
        return "초기 성장"
    if _has(text, ["ai", "organoid", "nam", "pbpk", "midd", "adc", "protac"]):
        return "기술 전환"
    return "시장 모니터링"


def _modality(text: str) -> str:
    if _has(text, ["adc", "antibody-drug conjugate"]):
        return "ADC"
    if _has(text, ["protac", "molecular glue"]):
        return "PROTAC/Molecular Glue"
    if _has(text, ["rna", "mrna", "sirna"]):
        return "RNA therapeutics"
    if _has(text, ["cell therapy", "gene therapy", "세포치료", "유전자치료"]):
        return "Cell & Gene Therapy"
    if _has(text, ["radiopharmaceutical", "방사성"]):
        return "Radiopharmaceuticals"
    if _has(text, ["bispecific", "이중항체", "다중특이"]):
        return "Bispecific antibodies"
    if _has(text, ["ai drug", "ai 신약", "인공지능 신약"]):
        return "AI drug discovery"
    if _has(text, ["nam", "organoid", "organ-on-a-chip", "오가노이드"]):
        return "NAMs/Organoid"
    if _has(text, ["pgx", "pharmacogen", "약물유전체"]):
        return "PGx/Precision medicine"
    return "General pharma/biotech"


def _pipeline_stage(text: str) -> str:
    if _has(text, ["discovery", "hit-to-lead", "후보물질 탐색"]):
        return "Discovery"
    if _has(text, ["lead optimization", "최적화"]):
        return "Lead Optimization"
    if _has(text, ["preclinical", "비임상"]):
        return "Preclinical"
    if _has(text, ["ind-enabling", "ind 승인", "ind 제출", "ind"]):
        return "IND-enabling"
    if _has(text, ["phase 1", "phase i", "1상", "임상 1"]):
        return "Phase 1"
    if _has(text, ["phase 2", "phase ii", "2상", "임상 2"]):
        return "Phase 2"
    if _has(text, ["phase 3", "phase iii", "3상", "임상 3"]):
        return "Phase 3"
    if _has(text, ["nda", "bla", "품목허가", "허가 신청"]):
        return "NDA/BLA"
    if _has(text, ["approval", "approved", "승인", "허가"]):
        return "Approval"
    if _has(text, ["post-marketing", "real-world", "rwe", "시판 후"]):
        return "Post-marketing"
    return "Stage 미확인"


def _customer_type(text: str, signal: str) -> str:
    if signal == "Deal":
        return "기술이전·투자유치 추진 기업"
    if signal == "Regulatory":
        return "IND/허가·규제 대응 기업"
    if signal == "Assay":
        return "비임상·DMPK 수요 기업"
    if signal == "Precision":
        return "병원·검사기관·정밀의료팀"
    if _has(text, ["cdmo", "cro"]):
        return "CRO/CDMO 협업 후보"
    return "시장 모니터링 대상 기업"


def _spmed_service(text: str, signal: str) -> str:
    if signal == "Precision":
        return "PGx/약물유전자검사"
    if signal == "Regulatory":
        return "규제 대응형 비임상·ADME 패키지"
    if signal == "Assay" or _has(text, ["adme", "dmpk", "ddi", "cyp", "ugt"]):
        return "in vitro ADME/DDI, CYP/UGT"
    if signal == "Deal":
        return "기술이전 전 DMPK/ADME 자료 패키지"
    return "리드 모니터링·고객 발굴"


def _opportunity_score(text: str, signal: str, pipeline_stage: str) -> int:
    score = 2
    if signal in {"Deal", "Regulatory"}:
        score += 1
    if signal in {"Assay", "Precision"}:
        score += 1
    if pipeline_stage in {"Preclinical", "IND-enabling", "Phase 1", "Phase 2", "NDA/BLA", "Approval"}:
        score += 1
    if _has(text, ["기술수출", "기술이전", "투자", "m&a", "licensing", "deal", "guidance", "가이드라인", "ind"]):
        score += 1
    return max(1, min(5, score))


def _next_action(score: int, service: str) -> str:
    if score >= 5:
        return f"바로 컨택 후보 · {service} 자료 송부"
    if score == 4:
        return f"영업 소재로 저장 · {service} 연결"
    if score == 3:
        return "후속 뉴스 모니터링 후 연락 후보로 검토"
    return "시장 참고 자료로 보관"


def _risk_note(signal: str) -> str:
    notes = {
        "Deal": "동일 이벤트 반복 기사 여부와 실제 계약 조건 확인",
        "Regulatory": "적용 범위와 시행 시점 확인",
        "Assay": "시험 수요가 개발 단계와 직접 연결되는지 확인",
        "Precision": "검사 도입 주체와 처방 연계성을 확인",
        "Market": "단순 시장 기사인지 고객 액션으로 이어지는지 확인",
    }
    return notes.get(signal, notes["Market"])


def _build_actions(high_priority: list[dict], topics: list[dict]) -> list[dict]:
    actions = []
    sorted_items = sorted(high_priority, key=lambda item: item["opportunityScore"], reverse=True)
    for item in sorted_items[:5]:
        actions.append(
            {
                "title": item["title"],
                "meta": f"{item['topicLabel']} · Score {item['opportunityScore']}/5 · {item['signal']}",
                "body": item["nextAction"],
                "link": item["link"],
            }
        )

    covered = {action["meta"].split(" · ")[0] for action in actions}
    for topic in topics:
        if topic["label"] in covered:
            continue
        if topic["count"] == 0:
            actions.append(
                {
                    "title": f"{topic['label']} 자료 보강",
                    "meta": "Watchlist",
                    "body": "검색 기간을 늘리거나 고객사·서비스 키워드를 추가해 수집 범위를 보강",
                    "link": "",
                }
            )
    return actions[:7]


def _extract_summary(markdown: str) -> list[str]:
    match = re.search(r"## 오늘의 핵심 요약\s+(.+?)(?:\n## |\Z)", markdown, re.S)
    if not match:
        return []
    return [
        re.sub(r"^-+\s*", "", line).strip()
        for line in match.group(1).splitlines()
        if line.strip().startswith("-")
    ][:4]


def _contains(item: dict, needles: list[str]) -> bool:
    text = f"{item['title']} {item['summary']} {item['source']}".lower()
    return _has(text, needles)


def _has(text: str, needles: list[str]) -> bool:
    return any(needle.lower() in text for needle in needles)


def _json_for_script(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def _html(data: dict) -> str:
    payload = _json_for_script(data)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>제약·바이오 BD 인사이트 대시보드</title>
  <style>
    :root {{
      --paper: #f7f8f5;
      --surface: #ffffff;
      --ink: #1b2420;
      --muted: #68736e;
      --line: #dce2dc;
      --green: #1f8a67;
      --teal: #007f86;
      --coral: #d85b48;
      --gold: #b48622;
      --blue: #4866c8;
      --shadow: 0 18px 45px rgba(31, 42, 36, 0.08);
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      min-width: 320px;
      color: var(--ink);
      background:
        linear-gradient(90deg, rgba(31, 138, 103, 0.07) 0 1px, transparent 1px 100%),
        linear-gradient(0deg, rgba(216, 91, 72, 0.055) 0 1px, transparent 1px 100%),
        var(--paper);
      background-size: 44px 44px;
      font-family: Arial, "Noto Sans KR", "Malgun Gothic", sans-serif;
      letter-spacing: 0;
    }}

    button, input {{
      font: inherit;
    }}

    .shell {{
      width: min(1440px, 100%);
      margin: 0 auto;
      padding: 22px;
    }}

    .topbar {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 18px;
      align-items: center;
      padding: 18px 0 20px;
      border-bottom: 1px solid var(--line);
    }}

    .eyebrow {{
      margin: 0 0 8px;
      color: var(--green);
      font-size: 13px;
      font-weight: 800;
    }}

    h1 {{
      margin: 0;
      font-size: 30px;
      line-height: 1.18;
      font-weight: 900;
    }}

    .date-pill {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 38px;
      padding: 0 14px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--surface);
      color: var(--muted);
      font-weight: 800;
      white-space: nowrap;
      box-shadow: var(--shadow);
    }}

    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin: 22px 0;
    }}

    .metric {{
      min-height: 112px;
      padding: 17px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}

    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
    }}

    .metric strong {{
      display: block;
      margin-top: 10px;
      font-size: 34px;
      line-height: 1;
      font-weight: 900;
    }}

    .metric i {{
      display: block;
      margin-top: 10px;
      color: var(--muted);
      font-size: 12px;
      font-style: normal;
      line-height: 1.4;
    }}

    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      gap: 22px;
      align-items: start;
    }}

    .section-title {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      margin: 0 0 14px;
    }}

    .section-title h2 {{
      margin: 0;
      font-size: 18px;
      line-height: 1.3;
    }}

    .tools {{
      display: grid;
      grid-template-columns: minmax(180px, 1fr) auto;
      gap: 10px;
      margin: 0 0 14px;
    }}

    .search {{
      width: 100%;
      height: 42px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0 13px;
      background: var(--surface);
      color: var(--ink);
      outline: none;
    }}

    .toggle {{
      height: 42px;
      min-width: 126px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      color: var(--ink);
      font-weight: 800;
      cursor: pointer;
    }}

    .toggle.active {{
      border-color: var(--coral);
      color: var(--coral);
      background: #fff4f1;
    }}

    .tabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 0 0 16px;
    }}

    .tab {{
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--surface);
      color: var(--muted);
      padding: 0 13px;
      font-weight: 800;
      cursor: pointer;
      white-space: nowrap;
    }}

    .tab.active {{
      border-color: var(--green);
      background: #eef8f3;
      color: var(--green);
    }}

    .article-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}

    .article {{
      min-height: 212px;
      display: grid;
      grid-template-rows: auto auto minmax(48px, 1fr) auto;
      gap: 10px;
      padding: 16px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}

    .article-head {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
    }}

    .chip {{
      flex: 0 0 auto;
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      border-radius: 999px;
      padding: 0 9px;
      color: var(--surface);
      background: var(--teal);
      font-size: 12px;
      font-weight: 900;
    }}

    .chip.Deal {{ background: var(--coral); }}
    .chip.Regulatory {{ background: var(--blue); }}
    .chip.Assay {{ background: var(--green); }}
    .chip.Precision {{ background: var(--gold); }}
    .chip.Market {{ background: var(--teal); }}

    .article h3 {{
      margin: 0;
      font-size: 16px;
      line-height: 1.42;
    }}

    .article p {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.58;
    }}

    .insight-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 7px;
      margin-top: 2px;
    }}

    .insight {{
      min-height: 48px;
      padding: 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfa;
    }}

    .insight b {{
      display: block;
      margin-bottom: 4px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.2;
    }}

    .insight span {{
      display: block;
      color: var(--ink);
      font-size: 12px;
      font-weight: 900;
      line-height: 1.3;
      overflow-wrap: anywhere;
    }}

    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }}

    .article a {{
      color: var(--ink);
      font-weight: 900;
      text-decoration: none;
    }}

    .article a:hover {{
      color: var(--green);
      text-decoration: underline;
      text-underline-offset: 3px;
    }}

    .empty {{
      display: none;
      padding: 30px;
      border: 1px dashed var(--line);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.7);
      color: var(--muted);
      text-align: center;
      font-weight: 800;
    }}

    .side {{
      display: grid;
      gap: 22px;
    }}

    .chart, .actions, .summary {{
      border-top: 3px solid var(--ink);
      padding-top: 14px;
    }}

    .bars {{
      display: grid;
      gap: 10px;
    }}

    .bar-row {{
      display: grid;
      grid-template-columns: 128px minmax(0, 1fr) 28px;
      gap: 10px;
      align-items: center;
      min-height: 28px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }}

    .bar-track {{
      height: 12px;
      background: rgba(27, 36, 32, 0.08);
      border-radius: 999px;
      overflow: hidden;
    }}

    .bar-fill {{
      height: 100%;
      min-width: 4px;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--green), var(--coral));
    }}

    .matrix {{
      position: relative;
      height: 178px;
      margin-top: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background:
        linear-gradient(90deg, transparent 49%, var(--line) 49% 50%, transparent 50%),
        linear-gradient(0deg, transparent 49%, var(--line) 49% 50%, transparent 50%),
        var(--surface);
      overflow: hidden;
    }}

    .dot {{
      position: absolute;
      width: 13px;
      height: 13px;
      border-radius: 50%;
      border: 2px solid var(--surface);
      box-shadow: 0 0 0 1px rgba(27, 36, 32, 0.25);
      transform: translate(-50%, -50%);
    }}

    .action-list, .summary-list {{
      display: grid;
      gap: 10px;
      margin: 0;
      padding: 0;
      list-style: none;
    }}

    .action {{
      padding: 13px 0;
      border-bottom: 1px solid var(--line);
    }}

    .action:last-child {{
      border-bottom: 0;
    }}

    .action a, .action strong {{
      display: block;
      color: var(--ink);
      font-size: 14px;
      font-weight: 900;
      line-height: 1.45;
      text-decoration: none;
    }}

    .action a:hover {{
      color: var(--green);
      text-decoration: underline;
      text-underline-offset: 3px;
    }}

    .action span {{
      display: block;
      margin: 4px 0;
      color: var(--green);
      font-size: 12px;
      font-weight: 900;
    }}

    .action p, .summary-list li {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
    }}

    @media (max-width: 1060px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}

      .side {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}

    @media (max-width: 760px) {{
      .shell {{
        padding: 16px;
      }}

      .topbar, .tools {{
        grid-template-columns: 1fr;
      }}

      .metrics, .article-grid, .side {{
        grid-template-columns: 1fr;
      }}

      h1 {{
        font-size: 24px;
      }}

      .metric {{
        min-height: 96px;
      }}

      .bar-row {{
        grid-template-columns: 104px minmax(0, 1fr) 26px;
      }}
    }}
  </style>
</head>
<body>
  <script id="dashboard-data" type="application/json">{payload}</script>
  <main class="shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">SPMED BD MONITOR</p>
        <h1>제약·바이오 인사이트 대시보드</h1>
      </div>
      <div class="date-pill" id="datePill"></div>
    </header>

    <section class="metrics" id="metrics"></section>

    <section class="layout">
      <div>
        <div class="section-title">
          <h2>수집 자료</h2>
        </div>
        <div class="tools">
          <input class="search" id="search" type="search" placeholder="회사, 키워드, 출처 검색">
          <button class="toggle" id="priorityToggle" type="button">우선순위</button>
        </div>
        <nav class="tabs" id="tabs" aria-label="Topic filters"></nav>
        <div class="article-grid" id="articleGrid"></div>
        <div class="empty" id="empty">표시할 자료가 없습니다.</div>
      </div>

      <aside class="side">
        <section class="summary">
          <div class="section-title"><h2>핵심 요약</h2></div>
          <ul class="summary-list" id="summaryList"></ul>
        </section>

        <section class="chart">
          <div class="section-title"><h2>주제별 신호</h2></div>
          <div class="bars" id="bars"></div>
          <div class="matrix" id="matrix" aria-label="Signal matrix"></div>
        </section>

        <section class="actions">
          <div class="section-title"><h2>BD 액션 큐</h2></div>
          <ul class="action-list" id="actions"></ul>
        </section>
      </aside>
    </section>
  </main>

  <script>
    const data = JSON.parse(document.getElementById("dashboard-data").textContent);
    const state = {{ topic: "all", query: "", priorityOnly: false }};
    const colorMap = {{
      Deal: "#d85b48",
      Regulatory: "#4866c8",
      Assay: "#1f8a67",
      Precision: "#b48622",
      Market: "#007f86"
    }};

    const byId = (id) => document.getElementById(id);
    const cleanDate = (value) => value || "unknown";

    function setText(node, text) {{
      node.textContent = text;
      return node;
    }}

    function render() {{
      byId("datePill").textContent = data.generatedLabel;
      renderMetrics();
      renderTabs();
      renderSummary();
      renderBars();
      renderMatrix();
      renderActions();
      renderArticles();
    }}

    function renderMetrics() {{
      const metrics = [
        ["수집 자료", data.metrics.totalItems, "오늘 브리핑에 반영된 링크"],
        ["우선 연락", data.metrics.highPriority, "기술이전·허가·임상 신호"],
        ["규제 자료", data.metrics.regulatory, "FDA·MFDS·가이던스 관련"],
        ["활성 주제", `${{data.metrics.activeTopics}}/${{data.topics.length}}`, "자료가 잡힌 모니터링 축"]
      ];
      if (data.database && data.database.totalArticles !== undefined) {{
        metrics.push([
          "누적 DB",
          data.database.totalArticles,
          `${{data.database.totalRuns}}회 실행 기록`
        ]);
      }}
      byId("metrics").replaceChildren(...metrics.map(([label, value, note]) => {{
        const card = document.createElement("article");
        card.className = "metric";
        card.append(setText(document.createElement("span"), label));
        card.append(setText(document.createElement("strong"), String(value)));
        card.append(setText(document.createElement("i"), note));
        return card;
      }}));
    }}

    function renderTabs() {{
      const tabs = [{{ key: "all", label: "전체", count: data.items.length }}, ...data.topics];
      byId("tabs").replaceChildren(...tabs.map((topic) => {{
        const button = document.createElement("button");
        button.type = "button";
        button.className = `tab ${{state.topic === topic.key ? "active" : ""}}`;
        button.textContent = `${{topic.label}} ${{topic.count}}`;
        button.addEventListener("click", () => {{
          state.topic = topic.key;
          renderTabs();
          renderArticles();
        }});
        return button;
      }}));
    }}

    function renderArticles() {{
      const query = state.query.trim().toLowerCase();
      const filtered = data.items.filter((item) => {{
        const topicMatch = state.topic === "all" || item.topicKey === state.topic;
        const priorityMatch = !state.priorityOnly || item.priority === "high";
        const haystack = `${{item.title}} ${{item.summary}} ${{item.source}} ${{item.topicLabel}} ${{item.marketArea}} ${{item.pipelineStage}} ${{item.customerType}} ${{item.service}}`.toLowerCase();
        const queryMatch = !query || haystack.includes(query);
        return topicMatch && priorityMatch && queryMatch;
      }});

      byId("empty").style.display = filtered.length ? "none" : "block";
      byId("articleGrid").replaceChildren(...filtered.map(renderArticle));
    }}

    function renderArticle(item) {{
      const article = document.createElement("article");
      article.className = "article";

      const head = document.createElement("div");
      head.className = "article-head";
      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = `${{item.topicLabel}} · ${{item.priority === "high" ? "High" : "Medium"}}`;
      const chip = document.createElement("span");
      chip.className = `chip ${{item.signal}}`;
      chip.textContent = item.signal;
      head.append(meta, chip);

      const title = document.createElement("h3");
      const link = document.createElement("a");
      link.href = item.link;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = item.title;
      title.append(link);

      const summary = document.createElement("p");
      summary.textContent = item.summary || item.angle;

      const insightGrid = document.createElement("div");
      insightGrid.className = "insight-grid";
      [
        ["BD Score", `${{item.opportunityScore}}/5`],
        ["시장", `${{item.marketArea}} · ${{item.marketStage}}`],
        ["단계", item.pipelineStage],
        ["고객군", item.customerType],
        ["SPMED", item.service],
        ["액션", item.nextAction]
      ].forEach(([label, value]) => {{
        const box = document.createElement("div");
        box.className = "insight";
        const key = document.createElement("b");
        key.textContent = label;
        const val = document.createElement("span");
        val.textContent = value;
        box.append(key, val);
        insightGrid.append(box);
      }});

      const bottom = document.createElement("div");
      bottom.className = "meta";
      bottom.textContent = `${{item.source}} · ${{cleanDate(item.published)}} · ${{item.riskNote}}`;

      article.append(head, title, summary, insightGrid, bottom);
      return article;
    }}

    function renderSummary() {{
      const items = data.summary.length ? data.summary : ["오늘 수집 자료를 BD 관점으로 확인하고 우선 연락 후보를 고르세요."];
      byId("summaryList").replaceChildren(...items.map((text) => {{
        const li = document.createElement("li");
        li.textContent = text;
        return li;
      }}));
    }}

    function renderBars() {{
      const max = Math.max(1, ...data.topics.map((topic) => topic.count));
      byId("bars").replaceChildren(...data.topics.map((topic) => {{
        const row = document.createElement("div");
        row.className = "bar-row";
        const label = setText(document.createElement("span"), topic.label);
        const track = document.createElement("div");
        track.className = "bar-track";
        const fill = document.createElement("div");
        fill.className = "bar-fill";
        fill.style.width = `${{Math.max(4, (topic.count / max) * 100)}}%`;
        track.append(fill);
        const count = setText(document.createElement("span"), String(topic.count));
        row.append(label, track, count);
        return row;
      }}));
    }}

    function renderMatrix() {{
      const matrix = byId("matrix");
      matrix.replaceChildren(...data.items.slice(0, 36).map((item, index) => {{
        const topicIndex = data.topics.findIndex((topic) => topic.key === item.topicKey);
        const x = 18 + topicIndex * 21 + ((index % 3) * 4);
        const y = item.priority === "high" ? 30 + ((index % 5) * 7) : 62 + ((index % 9) * 8);
        const dot = document.createElement("span");
        dot.className = "dot";
        dot.style.left = `${{Math.min(92, x)}}%`;
        dot.style.top = `${{Math.min(88, y)}}%`;
        dot.style.background = colorMap[item.signal] || colorMap.Market;
        dot.title = `${{item.signal}} · ${{item.title}}`;
        return dot;
      }}));
    }}

    function renderActions() {{
      byId("actions").replaceChildren(...data.actions.map((item) => {{
        const li = document.createElement("li");
        li.className = "action";
        const titleNode = item.link ? document.createElement("a") : document.createElement("strong");
        if (item.link) {{
          titleNode.href = item.link;
          titleNode.target = "_blank";
          titleNode.rel = "noreferrer";
        }}
        titleNode.textContent = item.title;
        const meta = setText(document.createElement("span"), item.meta);
        const body = setText(document.createElement("p"), item.body);
        li.append(titleNode, meta, body);
        return li;
      }}));
    }}

    byId("search").addEventListener("input", (event) => {{
      state.query = event.target.value;
      renderArticles();
    }});

    byId("priorityToggle").addEventListener("click", () => {{
      state.priorityOnly = !state.priorityOnly;
      byId("priorityToggle").classList.toggle("active", state.priorityOnly);
      renderArticles();
    }});

    render();
    window.setInterval(() => window.location.reload(), 10 * 60 * 1000);
  </script>
</body>
</html>
"""
