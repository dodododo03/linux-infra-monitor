FROM python:3.12-slim

# 로그가 버퍼링되지 않고 docker logs에 바로 보이도록
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# requirements를 먼저 복사 → 코드만 바뀌면 의존성 설치 레이어는 캐시 재사용
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY collector.py .

# root가 아닌 일반 사용자로 실행 (호스트 루트는 읽기 전용으로만 마운트)
RUN useradd --system --no-create-home monitor
USER monitor

CMD ["python", "collector.py"]
