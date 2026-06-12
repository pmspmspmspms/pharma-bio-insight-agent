# GitHub Actions 서버 자동화 등록 방법

이 프로젝트를 로컬 PC가 아니라 GitHub 서버에서 매일 실행하는 방법입니다.

## 목표 구조

```text
GitHub Actions
→ 매일 오전 9시 실행
→ Naver News API + MFDS RSS + Google News RSS 수집
→ SQLite DB 누적
→ Markdown 브리핑 생성
→ dashboard/index.html 생성
→ GitHub Pages로 대시보드 배포
```

## 1. GitHub 저장소 만들기

GitHub에서 새 저장소를 만듭니다.

추천:

```text
Repository name: pharma-bio-insight-agent
Visibility: Private
```

대시보드가 외부에 공개되어도 괜찮을 때만 Public으로 만드세요.

## 2. 업로드할 파일

업로드할 루트는 이 폴더의 내용물입니다.

```text
pharma-bio-insight-agent/
```

반드시 업로드하지 말아야 할 파일:

```text
.env
env.txt
local.env
data/
briefings/
logs/
```

API 키가 들어 있는 파일은 GitHub에 올리면 안 됩니다.

## 3. GitHub Secrets 등록

GitHub 저장소에서 아래 메뉴로 이동합니다.

```text
Settings
→ Secrets and variables
→ Actions
→ Repository secrets
```

필수로 등록:

```text
NAVER_CLIENT_ID
NAVER_CLIENT_SECRET
OPENAI_API_KEY
```

선택으로 등록:

```text
SLACK_WEBHOOK_URL
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
EMAIL_FROM
EMAIL_TO
```

## 4. GitHub Variables 등록

같은 화면에서 Variables 탭에 들어갑니다.

추천 변수:

```text
OPENAI_MODEL=gpt-5-mini
```

OpenAI 비용 없이 규칙 기반 대시보드만 만들고 싶으면 아래 변수도 추가합니다.

```text
DAILY_RUN_ARGS=--no-ai
```

AI 요약 리포트까지 원하면 `DAILY_RUN_ARGS`는 만들지 마세요.

## 5. GitHub Pages 설정

GitHub 저장소에서:

```text
Settings
→ Pages
→ Build and deployment
→ Source: GitHub Actions
```

으로 설정합니다.

## 6. 첫 실행

GitHub 저장소에서:

```text
Actions
→ Daily Pharma Bio Dashboard
→ Run workflow
```

를 누릅니다.

성공하면 Actions 실행 화면이나 Deploy 단계에서 GitHub Pages URL을 볼 수 있습니다.

보통 URL은 아래 형태입니다.

```text
https://<github-id>.github.io/pharma-bio-insight-agent/
```

## 7. 매일 자동 실행

workflow는 이미 한국시간 오전 9시에 맞춰져 있습니다.

```text
00:00 UTC = 09:00 Asia/Seoul
```

매일 실행되면:

```text
briefings/*.md
briefings/dashboard/index.html
data/insights.sqlite
```

가 생성되고, 대시보드는 GitHub Pages에 배포됩니다.

## 8. DB 누적 방식

현재 서버 버전은 GitHub Actions cache로 SQLite DB를 복원/저장합니다.

작은 개인용 자동화에는 충분합니다. 다만 장기적으로 더 안정적인 누적 DB가 필요하면 Supabase/Postgres로 옮기는 편이 좋습니다.

## 9. 문제 확인

실패하면 GitHub의 Actions 실행 로그를 확인하세요.

자주 보는 원인:

- `NAVER_CLIENT_ID` 또는 `NAVER_CLIENT_SECRET` 누락
- `OPENAI_API_KEY` 누락 또는 모델명 오류
- GitHub Pages Source가 GitHub Actions로 설정되지 않음
- Public Pages에 민감한 대시보드를 공개한 경우
