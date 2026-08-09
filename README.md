# KIS Market Dashboard

한국투자증권(KIS) Open API 기반 KR / US 마켓 대시보드 프로젝트.

이 저장소에는 별도 실행 파일인 `indicator_tracker.py`도 포함되어 있습니다. 기존 KIS 대시보드와 섞지 않고, 장 마감 후 Discord에 보내는 장기 지표 리포트를 생성합니다.

## 지표 추적자

평일 18:00 KST에 한 번 실행하는 Discord용 리포트입니다. 한 번의 실행에서 차트별 고해상도 PNG 16장을 생성합니다.

- 투자자 수급: 외국인 누적 순매수와 4주 이동평균, 주체별 누적 순매수
- 국내시장: KOSPI 일봉·주봉, KOSDAQ·삼성전자·SK하이닉스 일봉
- 미국시장: NASDAQ Composite와 S&P 500 일봉·주봉
- 매크로: USD/KRW, USD/JPY 일간, 미국채 10년·국고채 3년·금(GLD) 주간

각 PNG에는 차트 하나만 크게 배치합니다. iPhone 16 Pro의 Discord 전체 화면 뷰어에서 상단 Dynamic Island와 하단 메시지·미리보기 패널을 피할 수 있도록 `1206×1407`(약 6:7) 안전 화면비로 출력합니다. KOSPI·NASDAQ Composite·S&P 500 주봉에만 기본 `9·26·52·26` 일목균형표(전환선·기준선·선행스팬 구름)를 함께 표시합니다. 내부 2배 supersampling으로 캔들과 곡선의 계단 현상을 줄입니다. Discord의 메시지당 첨부 제한을 고려해 `수급·국내시장 7장`, `미국 주가지수 4장`, `환율·금리·금 5장`의 세 메시지로 전송합니다.

데이터 원천은 차트별로 고정되어 있습니다. Toss는 국내 지수·주식·국고채·GLD·투자자 수급에 사용하고, FRED는 NASDAQ Composite·S&P 500·역사 환율·미국 10년물에 사용합니다. 미국 지수 캔들은 같은 날짜의 FRED 지수값을 종가로 고정하고, NASDAQCOM은 Toss ONEQ, SP500은 Toss SPY의 OHLC를 `FRED close × ETF OHLC ÷ ETF close`로 합성합니다. 양쪽에 모두 있는 날짜만 사용하며 ETF 종가가 0인 날짜는 제외합니다. 다른 제공자로 대체하는 폴백은 없으며, 하나라도 실패하면 불완전한 리포트를 보내지 않고 실행 전체가 실패합니다.

Toss 키와 지표 추적자 전용 Discord 웹훅은 `~/.openclaw/secrets.json`에 아래 구조로 둡니다. 실제 값은 저장소 파일이나 cron 인자·환경변수에 복사하지 않습니다.

```json
{
  "providers": {
    "toss": {
      "client_id": "...",
      "client_secret": "...",
      "base_url": "https://openapi.tossinvest.com"
    },
    "discord": {
      "indicator_tracker_webhook_url": "https://discord.com/api/webhooks/.../..."
    }
  }
}
```

Toss WTS의 `설정 > Open API > 허용 IP`에도 실행 Mac의 공인 IP를 등록해야 합니다.

생성만 실행:

```bash
uv run python indicator_tracker.py generate
```

Discord 전송까지 실행:

```bash
bash scripts/indicator_tracker_send.sh
```

OpenClaw cron은 `Asia/Seoul` 기준 평일 18:00, 즉 `0 18 * * 1-5`에 위 래퍼를 한 번 실행하도록 등록합니다. 래퍼가 전용 Discord 웹훅으로 이미지 16장을 직접 전송하므로 cron 자체 delivery는 추가하지 않습니다.

## 목표
- 관심 종목 가격/등락률을 이미지 카드로 모니터링
- 장전 `NXT`, 정규장 `KRX`, 장후 `NXT` 흐름을 당일 캔들차트로 확인
- 미국장 관심 종목을 별도 watchlist로 분리해 5분봉 캔들차트로 확인
- **KIS API → JSON → native PNG** 구조로 유지

## 현재 구조
- `scripts/kis_market_dashboard_data.py`
  - KIS 토큰 발급
  - KR / US 시장별 현재가 조회
  - `NXT Pre → KRX → NXT Post` 또는 US 5분봉 당일 분봉 수집
  - 5분봉 OHLC JSON 생성
- `scripts/kis_market_dashboard_render.py`
  - Pillow 기반 네이티브 PNG 렌더러
  - 화이트 카드 UI 및 5분봉 캔들차트 생성
- `kis_market_dashboard.py`
  - 단일 CLI 엔트리포인트
  - 데이터 생성 / PNG 렌더 / 전송 / watchlist 관리
- `web_api/`
  - 별도 웹 대시보드 앱
  - 웹 백엔드가 `.env`를 런타임에 동적으로 로드하고 KIS를 직접 조회
  - CLI/artifact JSON 경로를 거치지 않는 live dashboard API 제공
- `pyproject.toml`
  - `uv` 기반 Python 의존성 관리

## 현재 기본 KR 카드 구성
- Samsung Electronics (005930)
- SK Hynix (000660)
- SK Telecom (017670)
- Hyundai Motor (005380)

## 현재 기본 US 카드 구성
- Apple (AAPL)
- Microsoft (MSFT)
- NVIDIA (NVDA)
- Tesla (TSLA)

## 환경 준비
```bash
uv sync
```

## 필요 환경변수
```bash
export KIS_APP_KEY="..."      # or KIS_APPKEY
export KIS_APP_SECRET="..."   # or KIS_APPSECRET
export KIS_BASE_URL="https://openapi.koreainvestment.com:9443"  # optional
# export KIS_BASE_URL="http://210.107.75.78:9443"  # KIS dev/sandbox example
# export KIS_ALLOW_UNSAFE_BASE_URL="1"  # only for local development against a trusted non-default endpoint
export KIS_CANO="..."               # optional, used for richer FX data paths
export KIS_ACNT_PRDT_CD="..."       # optional, used for richer FX data paths
export apiKey="..."                 # or ALPHAVANTAGE_API_KEY, for WTI summary card
```

OpenClaw로 바로 보내려면:
```bash
export OPENCLAW_TARGET="<telegram chat id>"
export OPENCLAW_CHANNEL="telegram"
export OPENCLAW_ACCOUNT="default"
```

## OpenClaw Agent Client Integration

이 저장소는 OpenClaw agent client에서 "로컬 repo + wrapper script" 조합으로 사용하는 방식이 가장 단순하고 관리하기 쉽습니다.

권장 구성은 다음과 같습니다.

1. 이 repo를 원하는 workspace 아래에 clone
2. workspace 쪽 wrapper script 하나를 둬서 `uv run python kis_market_dashboard.py generate ... --send` 를 감싼다
3. agent client에는 이 repo에 포함된 skill 또는 workspace local skill을 통해 "이 repo를 우선 사용하라"는 컨텍스트를 전달한다

예시 wrapper:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="/ABS/PATH/TO/workspace/kis-market-dashboard"
OUT_DIR="${KIS_DASHBOARD_OUT_DIR:-/ABS/PATH/TO/workspace/tmp}"
MARKET="${KIS_DASHBOARD_MARKET:-kr}"
TARGET="${OPENCLAW_TARGET:-channel:YOUR_CHANNEL_ID}"
CHANNEL="${OPENCLAW_CHANNEL:-discord}"
ACCOUNT="${OPENCLAW_ACCOUNT:-default}"

mkdir -p "$OUT_DIR"
cd "$ROOT"

exec uv run python kis_market_dashboard.py generate \
  --market "$MARKET" \
  --out-dir "$OUT_DIR" \
  --send \
  --target "$TARGET" \
  --channel "$CHANNEL" \
  --account "$ACCOUNT" \
  "$@"
```

### Bundled skill in this repo (`skills/kis-market-dashboard/SKILL.md`)

이 repo에는 재사용 가능한 skill 예시가 함께 포함되어 있습니다.

- path: `skills/kis-market-dashboard/SKILL.md`
- 다른 workspace로 repo를 옮겨도 함께 가져가 사용할 수 있음
- agent client가 workspace local skill만 읽는 환경이라면, 이 파일을 복사하거나 참조하여 local skill로 두면 됨

### Example local skill (`workspace/skills/kis-market-dashboard/SKILL.md`)

아래처럼 로컬 skill을 두면 agent client가 레거시 실험 스크립트 대신 이 repo를 우선 사용하도록 유도하기 좋습니다.

```md
---
name: kis-market-dashboard
description: Generate and send the KIS market dashboard using the local `kis-market-dashboard` repo and OpenClaw delivery. Use when the user asks for KR/US market dashboard generation, KIS dashboard image delivery to Discord/Telegram, watchlist updates, or debugging this dashboard pipeline.
---

# KIS Market Dashboard

Use the local repo-backed flow instead of rebuilding dashboard logic in-place.

## Default workflow

1. Use the wrapper script first:
   `/ABS/PATH/TO/workspace/scripts/kis_market_dashboard_send.sh`
2. The wrapper calls the repo CLI under:
   `/ABS/PATH/TO/workspace/kis-market-dashboard`
3. Generated artifacts land in:
   `/ABS/PATH/TO/workspace/tmp`

## Default command

```bash
bash /ABS/PATH/TO/workspace/scripts/kis_market_dashboard_send.sh
```

## Useful overrides

- KR vs US market:
  `KIS_DASHBOARD_MARKET=kr` or `KIS_DASHBOARD_MARKET=us`
- Custom output dir:
  `KIS_DASHBOARD_OUT_DIR=/ABS/PATH/TO/workspace/tmp`
- Custom OpenClaw delivery target:
  `OPENCLAW_TARGET=channel:...`
- Custom channel:
  `OPENCLAW_CHANNEL=discord` or `OPENCLAW_CHANNEL=telegram`
```

### OpenClaw cron job setup

OpenClaw에 cron 등록을 요청할 때는 "skill + wrapper + 시간대 + 시장별 스케줄"을 한 번에 알려주는 방식이 가장 안정적입니다.

아래는 그대로 복사해서 사용할 수 있는 프롬프트 예시입니다.

```text
`kis-market-dashboard` 스킬과 로컬 래퍼를 사용해서 KIS 마켓 대시보드 크론을 등록해줘.

사용할 진입점:
`bash /ABS/PATH/TO/workspace/scripts/kis_market_dashboard_send.sh`

참고 컨텍스트:
- 스킬: `/ABS/PATH/TO/kis-market-dashboard/skills/kis-market-dashboard/SKILL.md`
- 실제 repo: `/ABS/PATH/TO/workspace/kis-market-dashboard`
- 기본 Discord 대상: `channel:YOUR_CHANNEL_ID`
- 기본 채널: `discord`

중요:
- 시간대는 전부 `Asia/Seoul` 기준으로 처리해.
- 이미 비슷한 KIS dashboard cron job이 있으면 중복 생성하지 말고 update해.
- 이 래퍼 스크립트가 자체적으로 이미지를 보내므로, cron delivery는 중복 알림을 만들지 않게 설계해.

등록해야 할 스케줄:

1. KR 대시보드
- 한국 시간 기준 평일 오전 8시부터 저녁 8시까지
- 30분 간격
- 포함 시간 예시: 08:00, 08:30, 09:00 ... 19:30, 20:00
- `KIS_DASHBOARD_MARKET=kr` 로 실행

2. US 대시보드
- 한국 시간 기준 평일 오후 5시부터 밤 12시까지
- 1시간 간격
- 포함 시간 예시: 17:00, 18:00, 19:00, 20:00, 21:00, 22:00, 23:00, 00:00
- `KIS_DASHBOARD_MARKET=us` 로 실행
- 자정 00:00 실행은 다음 날로 넘어가는 점까지 반영해 정확하게 등록해

실행 방식:
- `/ABS/PATH/TO/workspace` 에서 exec로 실행
- isolated 세션 사용
- 실행 전에 필요한 경우 환경변수로 market만 주입
- 실행 명령:
  - KR:
    `KIS_DASHBOARD_MARKET=kr bash /ABS/PATH/TO/workspace/scripts/kis_market_dashboard_send.sh`
  - US:
    `KIS_DASHBOARD_MARKET=us bash /ABS/PATH/TO/workspace/scripts/kis_market_dashboard_send.sh`

원하는 결과:
- 실제 cron job들을 create/update 완료
- 각 job의 id, 이름, cron 표현식, 시간대, 실행 명령을 마지막에 간단히 요약
- KR 20:30은 제외되고 US 00:00은 반드시 포함되게 확인
```

## 실행
```bash
uv run python kis_market_dashboard.py generate
uv run python kis_market_dashboard.py generate --market us
```

## 웹 대시보드
웹 대시보드는 CLI와 별도로 동작합니다. 웹 요청 시점에 백엔드가 직접 KIS를 조회합니다.

실행:
```bash
cd web_api
uv run uvicorn app.main:create_app --factory --reload
```

필수 웹 환경변수:
```bash
export KIS_WEB_DASHBOARD_PASSWORD="..."
export KIS_WEB_DASHBOARD_SESSION_SECRET="..."
export KIS_WEB_DASHBOARD_INSECURE_HTTP=1  # local http cookie testing
```

웹 데이터용 런타임 env는 repo root `.env`에서 동적으로 로드합니다.

## 대시보드 예시

### 한국장 대시보드 예시
```bash
uv run python kis_market_dashboard.py generate --market kr
```

의도된 출력 구성:
- 상단 summary card: KOSPI / KOSDAQ / NASDAQ / USD-KRW / WTI
- 하단 stock card: 한국장 watchlist 4개 종목
- 장전 `NXT`, 정규장 `KRX`, 장후 `NXT` 흐름을 같은 카드에서 확인

텔레그램 전송 예시:
```bash
uv run python kis_market_dashboard.py generate \
  --market kr \
  --out-dir /ABS/PATH/TO/workspace/tmp \
  --send \
  --target <TARGET_ID_OR_CHANNEL> \
  --channel telegram \
  --account default
```

### 미국장 대시보드 예시
```bash
uv run python kis_market_dashboard.py generate --market us
```

의도된 출력 구성:
- 상단 summary card: 미국장 기준 주요 매크로/지표
- 하단 stock card: 미국장 watchlist 4개 종목
- 미국장 종목은 당일 5분봉 기준으로 카드형 캔들차트 렌더

텔레그램 전송 예시:
```bash
uv run python kis_market_dashboard.py generate \
  --market us \
  --out-dir /ABS/PATH/TO/workspace/tmp \
  --send \
  --target <TARGET_ID_OR_CHANNEL> \
  --channel telegram \
  --account default
```

### 출력 포맷 조정 예시
```bash
# WEBP 출력
uv run python kis_market_dashboard.py generate --market us --format webp

# 해상도 조정
uv run python kis_market_dashboard.py generate --market us --width-px 1440 --render-scale 3

# 렌더 생략(JSON만 생성)
uv run python kis_market_dashboard.py generate --market kr --no-render
```

## Watchlist CLI
현재 종목 리스트는 시장별로 로컬 `config/` 아래에서 관리합니다.
- `config/watchlist.kr.json`
- `config/watchlist.us.json`
- 이 파일들은 git에 올리지 않고, 없으면 CLI가 기본값으로 자동 생성합니다.

조회:
```bash
uv run python kis_market_dashboard.py watchlist list
uv run python kis_market_dashboard.py watchlist list --market us
```

추가:
```bash
uv run python kis_market_dashboard.py watchlist add 000270 Kia
uv run python kis_market_dashboard.py watchlist add --market us AAPL Apple --excd NAS
```

제거:
```bash
uv run python kis_market_dashboard.py watchlist remove 000270
uv run python kis_market_dashboard.py watchlist remove --market us AAPL
```

도움말:
```bash
uv run python kis_market_dashboard.py --help
uv run python kis_market_dashboard.py generate --help
uv run python kis_market_dashboard.py watchlist --help
```

- 기본적으로 `.venv/bin/python`을 사용합니다.
- `OPENCLAW_TARGET`이 있으면 이미지 전송
- 없으면 생성된 PNG 경로를 stdout으로 출력
- KIS access token cache is stored under `~/.cache/kis-market-dashboard/` with owner-only permissions and separated by endpoint/app key

생성 결과:
- `tmp/kis_market_dashboard.kr.json`
- `tmp/kis_market_dashboard.kr.png`
- `tmp/kis_market_dashboard.us.json`
- `tmp/kis_market_dashboard.us.png`

## Planned Features
- KOSDAQ / 환율 / 주요 지표 카드 추가
- 관심 종목 Watchlist 확장
- 시장 breadth / movers / sector overview
- 레이아웃 템플릿 다변화

## 참고
- 공식 샘플 저장소: https://github.com/koreainvestment/open-trading-api
- KIS Open API Portal: https://apiportal.koreainvestment.com/
