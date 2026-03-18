# KIS Market Dashboard

한국투자증권(KIS) Open API 기반 KR 마켓 대시보드 프로젝트.

## 목표
- 시장 주요 지수와 상태를 한눈에 확인
- 관심 종목 가격/등락률을 이미지 카드로 모니터링
- **KIS API → JSON → renderer → PNG** 구조로 유지

## 현재 구조
- `scripts/kis_market_dashboard_data.py`
  - KIS 토큰 발급
  - 국내 주식 현재가 조회
  - 코스피 보조 조회
  - renderer가 읽을 JSON 생성
- `renderer/index.html`
  - JSON 기반 카드 렌더러
- `scripts/kis_market_dashboard_image.sh`
  - JSON 생성 → renderer용 data 복사 → 스크린샷 → 전송

## 현재 카드 구성
- KOSPI
- Samsung Electronics (005930)
- SK Hynix (000660)
- SK Telecom (017670)

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
bash scripts/kis_market_dashboard_image.sh
```

- `OPENCLAW_TARGET`이 있으면 이미지 전송
- 없으면 생성된 PNG 경로를 stdout으로 출력

## JSON 스키마 예시
- `schemas/dashboard.example.json`

## Planned Features
- KOSDAQ / 환율 / 주요 지표 카드 추가
- 관심 종목 Watchlist 확장
- 시장 breadth / movers / sector overview
- 웹 대시보드 배포

## 참고
- 공식 샘플 저장소: https://github.com/koreainvestment/open-trading-api
- KIS Open API Portal: https://apiportal.koreainvestment.com/
