"""
리눅스 서버 리소스 수집기 (상시 실행 데몬)

- CPU / 메모리 / 디스크 사용률을 주기적으로 수집해 MariaDB에 저장
- 임계치를 연속 N회 넘으면 디스코드로 알람, 정상으로 돌아오면 복구 알림
- 같은 알람이 계속 울리지 않도록 재알림 간격(쿨다운) 적용
- SIGTERM(docker stop, systemctl stop)을 받으면 진행 중인 작업을 마치고 정상 종료
"""

import logging
import os
import queue
import signal
import socket
import threading
import time

import psutil
import pymysql
import requests

# ──────────────────────────────────────────────
# 설정: 전부 환경변수에서 읽는다 (코드에 비밀값을 두지 않는다)
# 필수 값은 os.environ[...] → 없으면 시작하자마자 실패 (fail-fast)
# ──────────────────────────────────────────────
DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.getenv("DB_PORT", "3307"))
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_NAME = os.getenv("DB_NAME", "infra_monitor")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

HOST_NAME = os.getenv("HOST_NAME") or socket.gethostname()
DISK_PATH = os.getenv("DISK_PATH", "/")  # 컨테이너에서는 호스트 루트를 마운트한 경로(/host)

COLLECT_INTERVAL = int(os.getenv("COLLECT_INTERVAL", "10"))  # 수집 주기(초)
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "80"))  # 임계치(%)
ALERT_CONSECUTIVE = int(os.getenv("ALERT_CONSECUTIVE", "3"))  # 연속 몇 번 넘어야 알람
# 연속 몇 번 정상이어야 복구로 보는지 (기본값은 ALERT_CONSECUTIVE와 같게)
ALERT_RECOVER_CONSECUTIVE = int(os.getenv("ALERT_RECOVER_CONSECUTIVE", str(ALERT_CONSECUTIVE)))
ALERT_REPEAT_MINUTES = int(os.getenv("ALERT_REPEAT_MINUTES", "30"))  # 재알림 간격
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "7"))  # DB 보관 기간

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("collector")

stop_event = threading.Event()


# ──────────────────────────────────────────────
# 알람 상태 관리
# ──────────────────────────────────────────────
class MetricAlert:
    """지표 하나(CPU, 메모리, 디스크)의 알람 상태를 기억한다."""

    def __init__(self, name: str):
        self.name = name
        self.over_count = 0  # 연속으로 임계치를 넘은 횟수
        self.under_count = 0  # 경고 중에 연속으로 정상 범위였던 횟수
        self.alerting = False  # 현재 알람 상태인지
        # 마지막 알람 전송 시각 (time.monotonic 기준)
        # time.time()은 NTP 동기화 등으로 시계가 바뀌면 쿨다운 계산이 틀어지므로 monotonic 사용
        self.last_sent = 0.0

    def update(self, value: float) -> None:
        now = time.monotonic()

        if value >= ALERT_THRESHOLD:
            self.over_count += 1
            self.under_count = 0  # 복구 대기 중이었다면 다시 처음부터 센다
            if not self.alerting and self.over_count >= ALERT_CONSECUTIVE:
                # 정상 → 경고: 처음 한 번 알림
                self.alerting = True
                self.last_sent = now
                notify(
                    f"🚨 **[경고] {self.name} 임계치 초과**\n"
                    f"> 호스트: `{HOST_NAME}`\n"
                    f"> 현재 {self.name}: **{value:.1f}%** (임계치 {ALERT_THRESHOLD:.0f}%)\n"
                    f"> {ALERT_CONSECUTIVE}회 연속 초과"
                )
            elif self.alerting and now - self.last_sent >= ALERT_REPEAT_MINUTES * 60:
                # 경고가 계속되는 중: 쿨다운이 지났을 때만 다시 알림
                self.last_sent = now
                notify(
                    f"⚠️ **[지속] {self.name} 여전히 임계치 초과**\n"
                    f"> 호스트: `{HOST_NAME}` | 현재 {self.name}: **{value:.1f}%**"
                )
        else:
            self.over_count = 0
            if self.alerting:
                # 한 번 내려간 걸로 바로 복구 처리하면 임계치 근처에서 경고/복구가 반복된다
                # → 연속 N회 정상일 때만 복구로 판단
                self.under_count += 1
                if self.under_count >= ALERT_RECOVER_CONSECUTIVE:
                    self.alerting = False
                    self.under_count = 0
                    notify(
                        f"✅ **[복구] {self.name} 정상화**\n"
                        f"> 호스트: `{HOST_NAME}` | 현재 {self.name}: **{value:.1f}%**\n"
                        f"> {ALERT_RECOVER_CONSECUTIVE}회 연속 정상"
                    )


# ──────────────────────────────────────────────
# 디스코드 알림 (백그라운드 전송)
# 메인 루프에서 직접 보내면 디스코드가 느릴 때 수집 주기가 밀린다.
# → 메인 루프는 큐에 넣기만 하고, 별도 스레드가 꺼내서 전송(실패 시 재시도)한다.
# ──────────────────────────────────────────────
SEND_RETRIES = 5  # 메시지 하나당 최대 전송 시도 횟수
alert_queue: "queue.Queue[str | None]" = queue.Queue(maxsize=100)


def notify(message: str) -> None:
    """알림을 큐에 넣고 바로 돌아온다 (메인 루프를 막지 않음)"""
    try:
        alert_queue.put_nowait(message)
    except queue.Full:
        log.error("알림 큐가 가득 참 → 알림 버림: %s", message.splitlines()[0])


def discord_worker() -> None:
    while True:
        message = alert_queue.get()
        if message is None:  # 종료 신호
            return
        for attempt in range(1, SEND_RETRIES + 1):
            if send_discord(message):
                break
            if attempt == SEND_RETRIES:
                log.error("디스코드 전송 %d회 실패 → 포기: %s", SEND_RETRIES, message.splitlines()[0])
                break
            # 재시도 간격을 5초, 10초, 20초, 40초로 늘린다 (디스코드 rate limit/장애 대비)
            # 종료 중이면 기다리지 않고 재시도를 포기한다
            if stop_event.wait(5 * 2 ** (attempt - 1)):
                log.warning("종료 중이라 재시도 중단: %s", message.splitlines()[0])
                break


def send_discord(message: str) -> bool:
    """전송 성공(또는 웹훅 미설정으로 의도적 생략)이면 True, 실패면 False"""
    if not DISCORD_WEBHOOK_URL: 
        log.warning("DISCORD_WEBHOOK_URL 미설정 → 알림 생략: %s", message.splitlines()[0])
        return True  # 설정 안 한 건 재시도해도 의미 없으므로 성공으로 취급
    try:
        # timeout이 없으면 디스코드가 응답하지 않을 때 수집기 전체가 멈춘다
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=5)
        if resp.ok:  # 웹훅은 보통 204지만, ?wait=true 등을 쓰면 200이 온다
            log.info("디스코드 알림 전송 성공")
            return True
        log.error("디스코드 알림 전송 실패 (HTTP %s)", resp.status_code)
    except requests.RequestException as e:
        log.error("디스코드 전송 에러: %s", e)
    return False


# ──────────────────────────────────────────────
# DB
# ──────────────────────────────────────────────
def get_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        connect_timeout=5,
    )


def save_metrics(cpu: float, mem: float, disk: float, is_alert: int) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO system_metrics"
                " (hostname, cpu_usage, mem_usage, disk_usage, is_alert)"
                " VALUES (%s, %s, %s, %s, %s)",
                (HOST_NAME, cpu, mem, disk, is_alert),
            )
        conn.commit()
    finally:
        conn.close()  # 예외가 나도 연결은 반드시 닫는다


def purge_old_metrics() -> None:
    """보관 기간이 지난 데이터 삭제 (테이블이 무한히 커지는 것 방지)"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            deleted = cur.execute(
                "DELETE FROM system_metrics WHERE created_at < NOW() - INTERVAL %s DAY",
                (RETENTION_DAYS,),
            )
        conn.commit()
        if deleted:
            log.info("오래된 데이터 %d건 삭제 (보관 %d일)", deleted, RETENTION_DAYS)
    finally:
        conn.close()


# ──────────────────────────────────────────────
# 메인 루프
# ──────────────────────────────────────────────
def handle_stop(signum, _frame):
    log.info("종료 신호(%s) 수신 → 현재 작업 마치고 종료합니다", signal.Signals(signum).name)
    stop_event.set()


def main() -> None:
    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    log.info(
        "수집기 시작 | host=%s disk=%s interval=%ss threshold=%.0f%% consecutive=%d",
        HOST_NAME, DISK_PATH, COLLECT_INTERVAL, ALERT_THRESHOLD, ALERT_CONSECUTIVE,
    )

    # daemon=True: 전송이 끝까지 안 끝나도 프로세스 종료를 막지 않는다
    worker = threading.Thread(target=discord_worker, name="discord-sender", daemon=True)
    worker.start()

    alerts = {
        "cpu": MetricAlert("CPU"),
        "mem": MetricAlert("메모리"),
        "disk": MetricAlert("디스크"),
    }

    # cpu_percent(interval=None)은 "직전 호출 이후 평균"을 돌려준다.
    # 첫 호출은 기준점을 잡는 용도라 값을 버린다.
    psutil.cpu_percent(interval=None)
    last_purge: float | None = None  # None = 아직 한 번도 정리 안 함 → 첫 주기에 정리

    while not stop_event.wait(COLLECT_INTERVAL):
        try:
            cpu = psutil.cpu_percent(interval=None)  # 수집 주기 전체의 평균 CPU
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage(DISK_PATH).percent
        except (OSError, psutil.Error) as e:
            # 예: DISK_PATH 마운트가 빠진 경우 → 데몬이 죽지 않고 다음 주기에 재시도
            log.error("리소스 수집 실패 (다음 주기에 재시도): %s", e)
            continue

        alerts["cpu"].update(cpu)
        alerts["mem"].update(mem)
        alerts["disk"].update(disk)
        is_alert = int(any(a.alerting for a in alerts.values()))

        try:
            save_metrics(cpu, mem, disk, is_alert)
            log.info("CPU %.1f%% | MEM %.1f%% | DISK %.1f%% | alert=%d", cpu, mem, disk, is_alert)

            if last_purge is None or time.monotonic() - last_purge >= 3600:  # 1시간마다 정리
                purge_old_metrics()
                last_purge = time.monotonic()
        except pymysql.MySQLError as e:
            # DB가 잠깐 죽어도 수집기는 죽지 않고 다음 주기에 다시 시도한다
            log.error("DB 저장 실패 (다음 주기에 재시도): %s", e)

    # 큐에 남은 알림을 마저 보내고 종료 (docker stop 기본 유예 10초 안에 끝나도록 최대 8초 대기)
    try:
        alert_queue.put(None, timeout=1)  # 종료 신호
    except queue.Full:
        pass  # 큐가 가득 차 있으면 기다리지 않고 종료 (daemon 스레드라 프로세스와 같이 끝남)
    worker.join(timeout=8)
    log.info("수집기 정상 종료")


if __name__ == "__main__":
    main()
