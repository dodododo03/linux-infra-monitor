@echo off
chcp 65001 >nul
rem ============================================================
rem  Windows 로컬 실행 스크립트 (Docker 없이)
rem  - .env 설정을 읽고, 이 PC의 MariaDB(127.0.0.1:3307)에 연결
rem  - 수집기 창 + 대시보드 창을 띄우고 브라우저를 연다
rem  - 끄려면: 각 창에서 Ctrl+C 또는 창 닫기
rem ============================================================
cd /d "%~dp0"

if not exist ".env" (
    echo [오류] .env 파일이 없습니다. .env.example 을 복사해서 .env 를 만들어 주세요.
    pause
    exit /b 1
)

rem .env 읽기 (# 으로 시작하는 줄은 주석으로 무시)
for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"

rem 로컬 실행용 덮어쓰기 (docker-compose.yml 에서는 compose 가 대신 설정함)
set "DB_HOST=127.0.0.1"
set "DB_PORT=3307"
set "DISK_PATH=C:\"
set "PYTHONIOENCODING=utf-8"

rem 처음 한 번만: 가상환경 만들고 라이브러리 설치
if not exist ".venv\Scripts\python.exe" (
    echo 처음 실행이라 가상환경을 만들고 라이브러리를 설치합니다...
    python -m venv .venv || (echo [오류] python 실행 실패 & pause & exit /b 1)
    ".venv\Scripts\python.exe" -m pip install -q -r collector\requirements.txt -r dashboard\requirements.txt || (echo [오류] 설치 실패 & pause & exit /b 1)
)

start "collector" ".venv\Scripts\python.exe" -u collector\collector.py
start "dashboard" ".venv\Scripts\python.exe" -m uvicorn --app-dir dashboard app:app --host 127.0.0.1 --port 8000

rem 대시보드가 뜰 시간을 잠깐 준 뒤 브라우저 열기
ping -n 4 127.0.0.1 >nul
start "" http://127.0.0.1:8000
echo 수집기와 대시보드를 새 창으로 실행했습니다. 끄려면 각 창에서 Ctrl+C 를 누르세요.
