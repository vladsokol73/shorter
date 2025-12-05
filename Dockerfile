FROM python:3.11-slim

WORKDIR /app

# Установка необходимых системных пакетов
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения и миграции
COPY ./app ./app
COPY ./alembic.ini .
COPY ./alembic ./alembic
COPY .env .env

# Создаем непривилегированного пользователя
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app

# Создаем скрипт для запуска
RUN echo '#!/bin/bash\n\
python -m alembic upgrade head\n\
uvicorn app.main:app --host 0.0.0.0 --port 8000' > /app/start.sh && \
    chmod +x /app/start.sh

# Переключаемся на непривилегированного пользователя
USER appuser

ENV PYTHONUNBUFFERED=1

# Открываем порт
EXPOSE 8000

# Запускаем приложение
CMD ["/app/start.sh"]
