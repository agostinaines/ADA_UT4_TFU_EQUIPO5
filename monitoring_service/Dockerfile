FROM python:3.12-slim

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONIOENCODING=utf-8 \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY monitoring_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common ./common
COPY monitoring_service/ .

EXPOSE 5004
CMD ["python", "main.py"]
