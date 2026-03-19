# KIS Market Dashboard

한국투자증권(KIS) Open API 기반 KR / US 마켓 대시보드 프로젝트.

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
  --out-dir /Users/seunghyuk/.openclaw/workspace/tmp \
  --send \
  --target <telegram_chat_id> \
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
  --out-dir /Users/seunghyuk/.openclaw/workspace/tmp \
  --send \
  --target <telegram_chat_id> \
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
