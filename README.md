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
export KIS_APPKEY="..."
export KIS_APPSECRET="..."
export KIS_BASE_URL="https://openapi.koreainvestment.com:9443"  # optional
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

## Watchlist CLI
현재 종목 리스트는 시장별로 따로 관리합니다.
- `config/watchlist.kr.json`
- `config/watchlist.us.json`

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

생성 결과:
- `tmp/kis_market_dashboard.kr.json`
- `tmp/kis_market_dashboard.kr.png`
- `tmp/kis_market_dashboard.us.json`
- `tmp/kis_market_dashboard.us.png`

## JSON 스키마 예시
- `schemas/dashboard.example.json`

## Planned Features
- KOSDAQ / 환율 / 주요 지표 카드 추가
- 관심 종목 Watchlist 확장
- 시장 breadth / movers / sector overview
- 레이아웃 템플릿 다변화

## 참고
- 공식 샘플 저장소: https://github.com/koreainvestment/open-trading-api
- KIS Open API Portal: https://apiportal.koreainvestment.com/
