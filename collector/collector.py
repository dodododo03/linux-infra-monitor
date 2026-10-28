import time
import psutil
import pymysql
import requests  # 디스코드 웹훅 전송용

# DB 설정 (기숙사 와이파이 IP 적용 완료)
DB_HOST = "192.168.1.105"
DB_USER = "monitor_user"
DB_PASSWORD = "1234"
DB_NAME = "infra_monitor"
DB_PORT = 3307

# [추가] 디스코드 웹훅 URL (아까 복사한 URL을 여기에 붙여넣으세요!)
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1564960016996245554/sa0MDd6BpMh_R7YgQYtdzwck1K4r_aqwIUA0NuTHAtz4QtYRkpXdxXm_SZJETLth6CAr"

# [추가] 알림 임계치 설정 (예: 80%)
ALERT_THRESHOLD = 80.0


def send_discord_alert(cpu, mem):
  """디스코드 채널로 경고 메시지를 전송하는 함수"""
  if "https://discord.com/api/webhooks/1564960016996245554/sa0MDd6BpMh_R7YgQYtdzwck1K4r_aqwIUA0NuTHAtz4QtYRkpXdxXm_SZJETLth6CAr":
    return  # URL이 설정 안 되어 있으면 무시

  content = {
      "content": (
          "🚨 **[긴급] CPU 임계치 초과!!!** 🚨\n"
          f"> 호스트: `dok-VMware-Virtual-Platform`\n"
          f"> 현재 CPU 사용량: **{cpu}%**\n"
          f"> 현재 메모리 사용량: **{mem}%**\n"
          f"> 임계치({ALERT_THRESHOLD}%)를 초과했습니다. 확인이 필요합니다!"
      )
  }

  try:
    response = requests.post(DISCORD_WEBHOOK_URL, json=content)
    if response.status_code == 204:
      print("[+] 디스코드 알림 전송 성공!")
    else:
      print(f"[-] 디스코드 알림 전송 실패 (코드: {response.status_code})")
  except Exception as e:
    print(f"[-] 디스코드 웹훅 에러: {e}")


def collect_metrics():
  try:
    # 1. 시스템 리소스 수집
    cpu_usage = psutil.cpu_percent(interval=1)
    mem_usage = psutil.virtual_memory().percent
    disk_usage = psutil.disk_usage("/").percent
    hostname = "dok-VMware-Virtual-Platform"

    # [추가] 임계치 초과 여부 확인 (CPU 또는 Mem이 80% 이상일 때)
    is_alert = 0
    if cpu_usage >= ALERT_THRESHOLD or mem_usage >= ALERT_THRESHOLD:
      is_alert = 1
      # 디스코드 알림 발송
      send_discord_alert(cpu_usage, mem_usage)

    # 2. MariaDB 연결
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT,
        charset="utf8mb4",
    )

    with connection.cursor() as cursor:
      # DB에 is_alert 컬럼을 포함하여 저장
      sql = """
                INSERT INTO system_metrics (hostname, cpu_usage, mem_usage,
                disk_usage, is_alert) 
                VALUES (%s, %s, %s, %s, %s)
            """
      cursor.execute(sql, (hostname, cpu_usage, mem_usage, disk_usage, is_alert))
      connection.commit()

    connection.close()
    print(
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Host: {hostname} | CPU:"
        f" {cpu_usage}% | Mem: {mem_usage}% | Disk: {disk_usage}% -> DB 저장 성공!"
    )

  except Exception as e:
    print(f"[-] 에러 발생: {e}")


if __name__ == "__main__":
  print("=== 리눅스 리소스 모니터링 수집기를 시작합니다 ===")
  collect_metrics()
