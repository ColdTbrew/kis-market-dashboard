# kis-market-dashboard

한국투자증권(KIS) Open API 기반 KR 마켓 대시보드 이미지 생성 스크립트.

## 기능
- KIS Open API로 국내 주식 현재가 조회
- 코스피는 공개 페이지에서 지수값 보완 조회
- 4패널 카드형 대시보드 PNG 생성
- 필요하면 OpenClaw/Telegram으로 이미지 전송

기본 구성:
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

## 파일
- `scripts/kis_market_dashboard_data.py` : KIS 토큰 발급 + 시세 조회 + JSON 생성
- `scripts/kis_market_dashboard_image.sh` : HTML 카드 대시보드 생성 + 스크린샷 + 전송

## 참고
- 공식 샘플 저장소: https://github.com/koreainvestment/open-trading-api
- KIS Open API Portal: https://apiportal.koreainvestment.com/
