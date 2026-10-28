# 파이썬 3.10 슬림 버전 이미지 사용
FROM python:3.10-slim

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 패키지 설치 (FastAPI, uvicorn, pymysql 등 필요한 라이브러리)
RUN pip install --no-cache-dir fastapi uvicorn pymysql psutil requests jinja2

# 웹 대시보드 소스코드 복사
COPY app.py /app/app.py
# (만약 templates나 static 폴더가 따로 있다면 COPY로 함께 복사해야 합니다!)

# FastAPI 외부 접속을 위한 포트 개방 (예: 8000번 포트)
EXPOSE 8000

# Uvicorn을 통해 FastAPI 서버 실행
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
