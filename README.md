# Linux Infra Monitor

리눅스 서버의 리소스 고갈(CPU 폭주, 메모리 부족, 디스크 풀)로 인한 장애를 예방하기 위해,
**24시간 상시 실행되며** 리소스를 수집·기록하고 임계치를 넘으면 디스코드로 알람을 보내는 모니터링 시스템입니다.

<!-- TODO: 대시보드 스크린샷 또는 GIF -->

## 아키텍처

```
┌──────────── Ubuntu Server ────────────────────────────────┐
│                                                           │
│  ┌───────────┐   INSERT    ┌──────────┐   SELECT  ┌──────────────┐
│  │ collector │ ──────────▶ │ MariaDB  │ ◀──────── │  dashboard   │ ◀── 브라우저 :8000
│  │ (psutil)  │             │ (내부망) │           │  (FastAPI)   │
│  └─────┬─────┘             └──────────┘           └──────────────┘
│        │ 호스트 / 를 읽기 전용 마운트(/host)                   │
│        │                                                  │
└────────┼──────────────────────────────────────────────────┘
         │ 임계치 초과 / 복구
         ▼
     Discord Webhook
```

모든 컨테이너는 `restart: unless-stopped`로 실행되어 프로세스가 죽거나 서버가 재부팅되어도 자동으로 다시 올라옵니다.

## 주요 기능

| 기능 | 설명 |
|---|---|
| 상시 수집 | 설정한 주기(기본 10초)마다 CPU·메모리·디스크 사용률 수집 |
| 오탐 방지 | 임계치를 **연속 N회**(기본 3회) 넘었을 때만 알람 → 순간 스파이크 무시 |
| 알람 폭탄 방지 | 경고 상태가 지속되면 **재알림 간격**(기본 30분)마다만 다시 알림 |
| 복구 알림 | 연속 N회 정상으로 돌아오면 ✅ 복구 메시지 전송 (임계치 근처에서 깜빡임 방지) |
| 장애 내성 | DB가 일시적으로 죽어도 수집기는 종료되지 않고 다음 주기에 재시도 |
| 정상 종료 | `SIGTERM` 수신 시 진행 중인 작업을 마치고 종료 (`docker stop` 대응) |
| 데이터 보관 | 보관 기간(기본 7일)이 지난 데이터 자동 삭제 |
| 보안 | 비밀값은 `.env`로 분리, DB 포트 외부 미노출, 컨테이너는 non-root 실행 |

## 기술 스택

- **Python 3.12** · psutil · PyMySQL
- **FastAPI** · Uvicorn · Chart.js
- **MariaDB 11**
- **Docker / Docker Compose**
- **GitHub Actions** (이미지 자동 빌드 · Docker Hub 푸시)

## 실행 방법

Docker와 Docker Compose가 설치된 Ubuntu 서버 기준입니다.

```bash
git clone https://github.com/dodododo03/linux-infra-monitor.git
cd linux-infra-monitor

cp .env.example .env
vi .env            # 디스코드 웹훅 URL, DB 비밀번호 등 입력

docker compose up -d --build
docker compose ps  # 3개 컨테이너 상태 확인
```

브라우저에서 `http://<서버IP>:8000` 접속

서버 재부팅 후에도 자동 실행되도록 Docker 서비스를 부팅 시 시작하게 설정합니다.

```bash
sudo systemctl enable docker
```

### Windows 로컬 실행 (Docker 없이, 개발/테스트용)

로컬 MariaDB(127.0.0.1:3307)에 `infra_monitor` DB와 계정이 있어야 합니다. `.env`를 만든 뒤 프로젝트 폴더의 `run-local.bat`을 더블클릭하면 됩니다.

- 처음 실행할 때 `.venv` 가상환경을 만들고 라이브러리를 설치합니다.
- 수집기 창과 대시보드 창이 새로 뜨고, 브라우저에서 `http://127.0.0.1:8000`이 열립니다.
- 끄려면 각 창에서 `Ctrl+C`를 누르거나 창을 닫습니다.

### 설정값 (`.env`)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `DISCORD_WEBHOOK_URL` | (없음) | 알람을 보낼 디스코드 웹훅 |
| `HOST_NAME` | 시스템 hostname | 알람과 DB에 기록될 서버 이름 |
| `COLLECT_INTERVAL` | 10 | 수집 주기(초) |
| `ALERT_THRESHOLD` | 80 | 알람 임계치(%) |
| `ALERT_CONSECUTIVE` | 3 | 연속 몇 회 초과 시 알람 |
| `ALERT_RECOVER_CONSECUTIVE` | (`ALERT_CONSECUTIVE`와 같음) | 경고 중 연속 몇 회 정상이면 복구 알림 |
| `ALERT_REPEAT_MINUTES` | 30 | 경고 지속 시 재알림 간격(분) |
| `RETENTION_DAYS` | 7 | 데이터 보관 기간(일) |

## 동작 테스트

```bash
# 로그 실시간 확인
docker compose logs -f collector

# CPU 부하를 걸어 알람 테스트 (60초간 모든 코어 100%)
sudo apt install -y stress
stress --cpu $(nproc) --timeout 60

# 자동 복구 테스트: 수집기를 강제로 죽여도 다시 올라오는지
docker kill $(docker compose ps -q collector)
docker compose ps
```

## 트러블슈팅

<!-- 직접 겪은 문제를 "증상 → 원인 → 해결" 순서로 기록 -->

### 1. 디스코드 알람이 한 번도 전송되지 않음
- **증상**: 임계치를 넘어도 디스코드 메시지가 오지 않음
- **원인**: 웹훅 URL 미설정 여부를 검사하는 조건문에 변수 대신 URL 문자열을 넣어, 비어 있지 않은 문자열이 항상 참이 되어 함수가 즉시 반환됨
- **해결**: `if not DISCORD_WEBHOOK_URL:`로 수정하고, 설정값을 환경변수로 분리

### 2. 컨테이너에서 측정한 디스크 사용량이 호스트와 다름
- **원인**: 컨테이너 안의 `/`는 호스트 디스크가 아니라 컨테이너의 overlay 파일시스템
- **해결**: 호스트 루트를 읽기 전용으로 `/host`에 마운트하고 해당 경로를 측정

## 개선 계획

- [ ] 서버로 자동 배포하는 CD 단계 추가
- [ ] 여러 서버를 한 대시보드에서 보기 (hostname별 필터)
- [ ] 디스크 사용률 그래프 추가
- [ ] Prometheus + Grafana 구성과 비교
