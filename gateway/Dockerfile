FROM python:3.12-slim

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONIOENCODING=utf-8 \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common ./common
COPY gateway/ .

EXPOSE 5000
CMD ["python", "main.py"]
