# Pharma Bio Insight Agent

제약·바이오 BD 관점으로 매일 볼 만한 자료를 수집하고 브리핑 Markdown으로 정리하는 기본 프로젝트입니다.

공유 링크의 요구사항에 BD 관점의 공식 규제 모니터링 축을 더했습니다.

- MFDS 규제·허가
- 제약·바이오 BD 동향
- in vitro ADME
- PGx / 약물유전자검사
- Recombinant Enzymes / CYP·UGT 효소

기본 수집원은 식약처 RSS와 Google News RSS입니다. 네이버 뉴스 API 키를 넣으면 한국 뉴스 수집 품질이 좋아지고, OpenAI API 키를 넣으면 단순 목록이 아니라 BD 활용 포인트 중심의 요약문으로 바뀝니다.

## 빠른 실행

```powershell
cd outputs/pharma-bio-insight-agent
python src/main.py --no-ai
```

이 명령은 API 키 없이도 실행되며 `briefings/` 폴더에 오늘 날짜의 Markdown 브리핑을 만듭니다.
동시에 `briefings/dashboard/index.html` 대시보드도 갱신됩니다.
수집 자료는 `data/insights.sqlite` SQLite DB에도 누적 저장됩니다.

OpenAI 요약까지 쓰려면:

```powershell
$env:OPENAI_API_KEY="sk-..."
$env:OPENAI_MODEL="gpt-5-mini"
python src/main.py
```

또는 `.env.example`을 복사해서 `.env` 파일을 만들고 값을 입력해도 됩니다.
Windows에서 `.env` 파일이 다른 프로그램으로 열리면 `env.txt`에 입력해도 됩니다.

```text
OPENAI_API_KEY=sk-...
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...
```

`.env`와 `env.txt`는 개인 키가 들어가는 파일이라 공유하거나 GitHub에 올리지 마세요. 이 프로젝트의 `.gitignore`에 둘 다 제외하도록 넣어뒀습니다.

## 환경 변수

`.env.example`을 참고해서 GitHub Secrets, 로컬 환경 변수, 또는 실행 환경에 값을 넣으면 됩니다.

필수는 없습니다. 다만 아래 값이 있으면 기능이 확장됩니다.

- `OPENAI_API_KEY`: AI 요약 생성
- `OPENAI_MODEL`: 기본값 `gpt-5-mini`
- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`: 네이버 뉴스 API 사용
- `BRIEFING_DB_PATH`: SQLite DB 저장 위치, 기본값 `data/insights.sqlite`
- `SLACK_WEBHOOK_URL`: Slack으로 브리핑 발송
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM`, `EMAIL_TO`: 이메일 발송

## 매일 자동 실행

`.github/workflows/daily-briefing.yml`을 GitHub 저장소에 올리면 매일 한국시간 오전 9시에 실행됩니다.

GitHub Actions Secrets에 최소한 `OPENAI_API_KEY`를 넣으면 AI 요약 브리핑이 생성됩니다. Slack이나 이메일로 받으려면 해당 발송용 Secret도 추가하세요.

로컬 PC에서 매일 자동 갱신하려면 Windows 작업 스케줄러를 등록할 수 있습니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_windows_task.ps1
```

등록 후 매일 오전 9시에 `scripts\run_dashboard_update.ps1`이 실행됩니다. 실행 로그는 `logs/dashboard-update.log`에 남습니다.

## 결과물 형식

브리핑은 다음 흐름으로 나옵니다.

1. 오늘의 핵심 요약
2. MFDS 규제·허가 공식 자료
3. 제약·바이오 BD 동향과 주제별 주요 자료 3~5개
4. 왜 중요한지
5. BD 대화 포인트
6. 출처 링크

## DB 저장

매번 실행할 때 SQLite DB에 실행 기록과 수집 자료가 저장됩니다.

기본 DB 위치:

```text
data/insights.sqlite
```

저장 테이블은 다음과 같습니다.

- `runs`: 실행 날짜, 생성 시각, 설정값, 생성 파일 경로
- `articles`: 고유 URL 기준으로 누적 저장되는 기사/공식 자료
- `run_articles`: 특정 실행에서 어떤 자료가 어떤 주제로 잡혔는지 연결

## 대시보드

`briefings/dashboard/index.html`을 브라우저에서 열면 최신 브리핑을 대시보드로 볼 수 있습니다.

화면에는 다음 요소가 포함됩니다.

- 전체 수집 자료, 우선 연락 신호, 규제 자료, 활성 주제 수
- 주제별 필터와 키워드 검색
- 우선순위 기사만 보는 토글
- 기사별 시장, 개발단계, 고객군, SPMED 연결 서비스
- BD Opportunity Score와 다음 액션
- 주제별 수집량 막대 차트
- BD 액션 큐

## 소스 조정

`src/config.py`의 `TOPICS`에서 검색어를 바꾸면 됩니다. 예를 들어 특정 회사, 고객사, 경쟁사, 서비스 키워드를 넣어 리드 발굴용으로 좁힐 수 있습니다.
