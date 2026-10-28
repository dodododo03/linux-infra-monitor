FROM python:3.10-slim
WORKDIR /app
RUN pip install --no-cache-dir pymysql psutil requests
COPY collector.py /app/collector.py
CMD ["python", "collector.py"]
