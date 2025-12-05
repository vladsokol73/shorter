#!/bin/bash

# Запускаем миграции
echo "Running database migrations..."
alembic upgrade head

# Запускаем приложение
echo "Starting FastAPI application..."
uvicorn main:app --host 0.0.0.0 --port 8000
