# KIS Market Dashboard 계획서

## 1. 프로젝트 개요

한국투자증권 API와 Supabase를 활용해 개인 투자용 웹 대시보드를 만든다.
목표는 시장 전반 흐름, 주요 지수, 관심 종목, 사용자 설정 정보를 한 화면에서 보기 좋게 제공하는 것이다.

배포는 Vercel을 사용하고, UI는 다크 테마 기반의 모던 대시보드 스타일로 구성한다.

---

## 2. 목표

### 핵심 목표
- 시장 상황을 한눈에 파악할 수 있는 대시보드 제공
- 관심 종목의 가격, 등락률, 거래량, 거래대금 등을 빠르게 확인
- 사용자별 관심 종목, 레이아웃, 설정을 저장
- Vercel에 배포해 브라우저에서 바로 사용 가능하도록 구성

### 사용자 경험 목표
- 3초 안에 시장 상태를 파악할 수 있어야 함
- 장중에 계속 켜두고 봐도 피로하지 않은 UI
- 모바일/데스크탑 모두 자연스럽게 동작

---

## 3. 기술 스택

### Frontend
- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui
- Recharts 또는 Tremor

### Backend / Infra
- Next.js Route Handlers
- Vercel
- Supabase Auth
- Supabase Postgres
- Supabase Storage (필요 시)

### External API
- 한국투자증권 API

---

## 4. 역할 분리

### 한국투자증권 API
- 국내 주식 시세 조회
- 주요 지수 조회
- 관심 종목 현재가/등락률 조회
- 추후 계좌/포지션 데이터 조회 가능성 검토

### Supabase
- 사용자 인증
- 사용자 프로필 저장
- 관심 종목 목록 저장
- 대시보드 레이아웃 및 설정 저장
- 알림 규칙 저장
- 추후 메모/전략 기록/사용자별 상태 저장

### Vercel
- 프론트엔드 배포
- 서버 API 라우트 실행
- 환경변수 관리

---

## 5. 시스템 구조

```text
Browser
  -> Next.js App (Vercel)
    -> Internal API Routes
      -> Korean Investment & Securities API
      -> Supabase
```

### 원칙
- 한국투자증권 API 키는 브라우저에 노출하지 않는다.
- KIS API 호출은 서버에서만 수행한다.
- 클라이언트는 내부 API만 호출한다.
- 사용자 데이터와 설정은 Supabase에 저장한다.

---

## 6. MVP 범위

### A. 마켓 개요 카드
- KOSPI
- KOSDAQ
- USD/KRW
- 필요 시 미국 선물/보조 지표

### B. 관심 종목 보드
- 종목명
- 종목코드
- 현재가
- 전일 대비
- 등락률
- 거래량
- 거래대금
- 시가/고가/저가

### C. 사용자 기능
- 로그인
- 관심 종목 추가/삭제
- 대시보드 기본 설정 저장
- 갱신 주기 저장

### D. UI/배포
- 다크 테마 대시보드
- 반응형 레이아웃
- Vercel 배포

---

## 7. 확장 기능

### 2단계
- 시장 breadth (상승/하락 종목 수)
- 거래량 급증 종목
- 급등/급락 종목
- 섹터 강도 요약
- 미니 차트 / 스파크라인

### 3단계
- 계좌 연동
- 보유 종목 평가손익
- 뉴스/공시 요약
- 가격 알림 / 조건 알림
- 사용자 메모/투자 아이디어 저장

---

## 8. 화면 구성 초안

### 1) 상단 헤더
- 현재 시각
- 장 상태 (장전 / 장중 / 장마감)
- 마지막 업데이트 시간

### 2) 주요 지수 카드 섹션
- KOSPI
- KOSDAQ
- 환율
- 기타 주요 지표

### 3) 관심 종목 보드
- 카드 또는 테이블 형태
- 등락률 색상 강조
- 거래대금/거래량 표시

### 4) 시장 강도 / 시그널 영역
- 상승/하락 종목 수
- 거래량 급증 종목
- 급등/급락 종목

### 5) 사용자 설정
- 관심 종목 편집
- 카드 순서 저장
- 다크/라이트 여부 (기본은 다크)

---

## 9. UI 방향

### 스타일 키워드
- 다크 테마
- 모던 금융 대시보드
- 숫자 강조형 카드 UI
- 고대비 + 깔끔한 정보 밀도

### 디자인 기준
- 상승: 녹색 계열
- 하락: 빨간색 계열
- 중립: 회색 계열
- 배경: 짙은 네이비/블랙
- 카드: 약한 보더 + 둥근 모서리 + 적당한 여백

---

## 10. Supabase 데이터 모델 초안

### profiles
- id
- email
- full_name
- created_at

### watchlists
- id
- user_id
- name
- created_at

### watchlist_items
- id
- watchlist_id
- symbol
- display_order
- created_at

### dashboard_preferences
- id
- user_id
- theme
- refresh_interval
- layout_json
- created_at
- updated_at

### alert_rules
- id
- user_id
- symbol
- condition_type
- condition_value
- enabled
- created_at

---

## 11. API 초안

### 내부 API
- `/api/market/overview`
- `/api/market/indexes`
- `/api/market/watchlist`
- `/api/market/movers`
- `/api/user/preferences`

### 원칙
- 브라우저는 내부 API만 호출
- 내부 API가 KIS API와 Supabase를 조합
- 캐시 전략 도입 고려

---

## 12. 개발 단계

### Step 1
- Next.js 프로젝트 생성
- Tailwind / shadcn/ui 설정
- 기본 라우팅 및 레이아웃 구성

### Step 2
- Supabase 연결
- Auth 구성
- 기본 테이블 스키마 작성

### Step 3
- 더미 데이터 기반 대시보드 UI 구현
- 카드/테이블/레이아웃 완성

### Step 4
- KIS API 연동
- 지수 / 종목 데이터 연결
- 서버 API 구성

### Step 5
- 관심 종목 CRUD
- 사용자 설정 저장
- 새로고침 주기/캐시 전략 반영

### Step 6
- Vercel 배포
- 환경변수 구성
- 운영 점검

---

## 13. 우선순위

### P0
- 프로젝트 뼈대 구성
- Supabase Auth 연결
- 관심 종목 저장 구조
- 주요 지수 카드 UI
- 관심 종목 보드 UI
- Vercel 배포

### P1
- KIS API 실데이터 연결
- 시장 breadth
- movers
- 미니 차트

### P2
- 계좌 연동
- 알림 규칙
- 뉴스/공시 요약
- 개인 메모/전략 기록

---

## 14. 성공 기준

- 로그인 후 개인화된 대시보드를 볼 수 있어야 함
- 관심 종목을 저장하고 다시 접속해도 유지되어야 함
- 주요 지수와 관심 종목 상태를 빠르게 파악할 수 있어야 함
- Vercel 배포 후 안정적으로 조회 가능해야 함

---

## 15. 다음 액션

1. Next.js 앱 초기화
2. Supabase 프로젝트 연결
3. 스키마 작성
4. 대시보드 더미 UI 구현
5. KIS API 연결
6. Vercel 배포
