# URL Shortener Service

Сервис для сокращения URL-адресов с поддержкой пользовательских доменов и API-ключей.

## Функциональность

- Сокращение длинных URL в короткие
- Управление пользовательскими доменами
- Перенаправление с корневого пути домена
- Защита API с помощью API-ключей
- Поддержка Docker

## API Endpoints

### Управление URL

- `POST /shorten` - Создание короткой ссылки
  ```json
  {
    "target_url": "https://example.com",
    "domain": "custom.com" // опционально
  }
  ```

- `GET /{short_code}` - Перенаправление по короткой ссылке

### Управление доменами

- `GET /domains` - Получение списка всех доменов
- `POST /domains` - Добавление нового домена
  ```json
  {
    "domain": "example.com",
    "redirect_url": "https://target-site.com"
  }
  ```
- `PUT /domains/{domain}` - Обновление настроек домена
  ```json
  {
    "redirect_url": "https://new-target.com"
  }
  ```
- `DELETE /domains/{domain}` - Удаление домена

## Запуск

1. Создайте файл `.env` с необходимыми переменными окружения:
   ```
   DATABASE_URL=mysql://user:password@db/urlshortener
   API_KEY=your-api-key
   ```

2. Запустите с помощью Docker Compose:
   ```bash
   docker-compose up -d
   ```

## Использование API

Для всех запросов необходимо указывать API-ключ в заголовке:
```
X-API-Key: your-api-key
```

### Примеры

1. Создание короткой ссылки:
   ```bash
   curl -X POST http://localhost:8000/shorten \
     -H "X-API-Key: your-api-key" \
     -H "Content-Type: application/json" \
     -d '{"target_url": "https://example.com"}'
   ```

2. Добавление домена с перенаправлением:
   ```bash
   curl -X POST http://localhost:8000/domains \
     -H "X-API-Key: your-api-key" \
     -H "Content-Type: application/json" \
     -d '{"domain": "example.com", "redirect_url": "https://google.com"}'
   ```

3. Обновление настроек домена:
   ```bash
   curl -X PUT http://localhost:8000/domains/example.com \
     -H "X-API-Key: your-api-key" \
     -H "Content-Type: application/json" \
     -d '{"redirect_url": "https://new-target.com"}'
   ```

4. Удаление домена:
   ```bash
   curl -X DELETE http://localhost:8000/domains/example.com \
     -H "X-API-Key: your-api-key"
   ```

## Особенности работы с доменами

- При переходе на корневой путь домена (`/`) происходит автоматическое перенаправление на указанный URL
- Для каждого домена можно создавать свои короткие ссылки
- Домены должны быть уникальными в системе
