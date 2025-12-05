from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security import APIKeyHeader
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy import create_engine, Column, String, Integer, Boolean, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import string
import random
from datetime import datetime, timedelta
import secrets
import os
from dotenv import load_dotenv
import hashlib
import requests
from requests.exceptions import RequestException
import logging
from typing import List, Optional
from sqlalchemy.pool import Pool
from sqlalchemy.exc import IntegrityError

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Мониторинг соединений с базой данных
def on_checkout(dbapi_conn, connection_record, connection_proxy):
    logger.info("Database connection checked out.")


@event.listens_for(Pool, "checkin")
def on_checkin(dbapi_conn, connection_record):
    logger.info("Database connection checked in.")


# Настройки безопасности
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Получаем API ключи из переменных окружения
API_KEY = os.getenv("API_KEY")
CREATE_ONLY_API_KEY = os.getenv("CREATE_ONLY_API_KEY")

if not API_KEY:
    raise ValueError("API_KEY not set in environment variables")

# Проверяем наличие CREATE_ONLY_API_KEY, но не блокируем запуск, если его нет
if not CREATE_ONLY_API_KEY:
    logger.warning("CREATE_ONLY_API_KEY not set in environment variables. Create-only API access will be disabled.")

# База данных
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/shortener.db")
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,  # увеличиваем размер пула
    max_overflow=30,  # увеличиваем максимальное количество дополнительных соединений
    pool_timeout=60,  # увеличиваем таймаут
    pool_recycle=3600,  # переиспользуем соединения каждый час
)

# Добавляем слушатели событий пула соединений
event.listen(engine.pool, 'checkout', on_checkout)
event.listen(engine.pool, 'checkin', on_checkin)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Модели SQLAlchemy
class URL(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, index=True)
    original_url = Column(String(2048), nullable=False)
    url_hash = Column(String(10), nullable=False, unique=True)
    short_code = Column(String(6), nullable=False, unique=True)
    created_at = Column(String(30), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)


class Domain(Base):
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(255), nullable=False, unique=True)
    redirect_url = Column(String(2048), nullable=False)
    created_at = Column(String(30), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)


Base.metadata.create_all(bind=engine)


# Pydantic модели
class URLBase(BaseModel):
    target_url: HttpUrl


class URLCreate(URLBase):
    custom_code: Optional[str] = None


class URLUpdate(BaseModel):
    target_url: Optional[HttpUrl] = None
    is_active: Optional[bool] = None
    short_code: Optional[str] = None


class URLResponse(BaseModel):
    target_url: HttpUrl
    short_code: str
    created_at: str
    is_active: bool


class DomainBase(BaseModel):
    domain: str
    redirect_url: HttpUrl


class DomainCreate(DomainBase):
    pass


class DomainUpdate(BaseModel):
    redirect_url: Optional[HttpUrl] = None
    is_active: Optional[bool] = None


class DomainResponse(DomainBase):
    id: int
    created_at: str
    is_active: bool


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_api_key(api_key: str = Security(api_key_header), require_full_access: bool = False) -> bool:
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key is required",
            headers={"WWW-Authenticate": API_KEY_NAME},
        )

    # Проверяем полноценный API ключ
    if api_key == API_KEY:
        return True

    # Проверяем ключ только для создания ссылок
    if not require_full_access and api_key == CREATE_ONLY_API_KEY:
        return True

    # Если ключ не подошел ни к одному из проверенных
    raise HTTPException(
        status_code=403,
        detail="Invalid API key or insufficient permissions",
        headers={"WWW-Authenticate": API_KEY_NAME},
    )


def create_random_code() -> str:
    """
    Создает случайный код длиной 6 символов из английских букв обоих регистров
    """
    # Используем только английские буквы обоих регистров (a-z, A-Z)
    letters = string.ascii_letters  # содержит 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    code_length = 6
    return ''.join(random.choice(letters) for _ in range(code_length))


def get_url_hash(url: str) -> str:
    """Создает числовой хеш для URL длиной 10 символов"""
    # Используем первые 10 цифр от MD5 хеша, преобразованного в число
    full_hash = hashlib.md5(str(url).encode()).hexdigest()
    # Преобразуем первые 8 символов хеша в число и берем последние 10 цифр
    numeric_hash = str(int(full_hash[:8], 16))[-10:].zfill(10)
    return numeric_hash


def verify_url(url: str) -> bool:
    """
    Проверяет доступность URL
    Возвращает True если URL доступен, False если нет
    """
    logger.info(f"Проверка доступности URL: {url}")
    try:
        # Делаем HEAD запрос с таймаутом в 5 секунд
        response = requests.head(url, timeout=5, allow_redirects=True)
        status_code = response.status_code
        logger.info(f"Ответ от URL {url}: статус {status_code}")
        return status_code < 400
    except RequestException as e:
        logger.error(f"Ошибка при проверке URL {url}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Неожиданная ошибка при проверке URL {url}: {str(e)}")
        # Возвращаем True, чтобы не блокировать создание короткой ссылки
        # при неожиданных ошибках проверки
        return True


# Константа для разрешенного домена
ALLOWED_DOCS_DOMAIN = "services.investingindigital.com"

app = FastAPI(
    title="URL Shortener API",
    redoc_url=None,  # Отключаем ReDoc полностью
    docs_url="/docs",  # Swagger UI будет доступен по /docs
    openapi_url="/api/openapi.json",
    root_path=os.getenv("ROOT_PATH", ""),
)


# Middleware для проверки доступа к документации
@app.middleware("http")
async def check_docs_access(request: Request, call_next):
    # Добавляем логирование состояния пула в начале запроса
    logger.info(f"Request to {request.url.path}.")

    if request.url.path in ["/docs", "/docs/oauth2-redirect", "/api/openapi.json"]:
        host = request.headers.get('host', '').split(':')[0]
        if host != ALLOWED_DOCS_DOMAIN:
            return JSONResponse(
                status_code=403,
                content={"detail": "Access to API documentation is not allowed from this domain"}
            )
    response = await call_next(request)

    # Логируем состояние пула после обработки запроса
    logger.info(f"Completed request to {request.url.path}.")

    return response


# Настройка CORS
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Константа для разрешенного домена
ALLOWED_DOMAIN = "services.investingindigital.com"


@app.get("/")
async def root(request: Request, db: Session = Depends(get_db)):
    # Получаем домен из заголовка Host
    host = request.headers.get('host', '').split(':')[0]

    # Ищем домен в базе данных
    domain = db.query(Domain).filter(
        Domain.domain == host,
        Domain.is_active == True
    ).first()

    # Если домен найден, делаем редирект
    if domain:
        return RedirectResponse(url=domain.redirect_url, status_code=302)

    # Если домен не найден, показываем приветственное сообщение
    return {"message": "Welcome to URL Shortener API"}


@app.get("/domains", response_model=List[DomainResponse])
async def list_domains(
        request: Request,
        db: Session = Depends(get_db),
        authenticated: bool = Depends(verify_api_key)
):
    # Получаем домен из заголовка Host
    host = request.headers.get('host', '').split(':')[0]

    # Проверяем, совпадает ли домен с разрешенным
    if host != ALLOWED_DOMAIN:
        raise HTTPException(
            status_code=403,
            detail="Access to domains list is not allowed from this domain"
        )

    domains = db.query(Domain).filter(Domain.is_active == True).all()
    return domains


@app.post("/domains", response_model=DomainResponse)
async def create_domain(
        domain: DomainCreate,
        db: Session = Depends(get_db),
        authenticated: bool = Depends(verify_api_key)
):
    # Проверяем, существует ли уже такой домен
    existing_domain = db.query(Domain).filter(Domain.domain == domain.domain).first()
    if existing_domain:
        raise HTTPException(
            status_code=400,
            detail="This domain is already registered"
        )

    # Создаем новую запись
    db_domain = Domain(
        domain=domain.domain,
        redirect_url=str(domain.redirect_url),
        created_at=datetime.utcnow().isoformat(),
        is_active=True
    )

    try:
        db.add(db_domain)
        db.commit()
        db.refresh(db_domain)
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Error creating domain redirect"
        )

    return DomainResponse(
        id=db_domain.id,
        domain=db_domain.domain,
        redirect_url=db_domain.redirect_url,
        created_at=db_domain.created_at,
        is_active=db_domain.is_active
    )


@app.delete("/domains/{domain_id}")
async def delete_domain(
        domain_id: int,
        db: Session = Depends(get_db),
        authenticated: bool = Depends(verify_api_key)
):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    domain.is_active = False
    db.commit()
    return {"status": "success"}


@app.delete("/domains/{domain}", response_model=DomainResponse)
async def delete_domain(
        domain: str,
        api_key: str = Security(api_key_header),
        db: Session = Depends(get_db)
):
    verify_api_key(api_key)

    # Проверяем существование домена
    domain_record = db.query(Domain).filter(Domain.domain == domain).first()
    if not domain_record:
        raise HTTPException(status_code=404, detail="Domain not found")

    # Удаляем домен
    db.delete(domain_record)
    db.commit()

    return domain_record


@app.post("/shorten", response_model=URLResponse)
async def create_short_url(
        url: URLCreate,
        db: Session = Depends(get_db),
        authenticated: bool = Depends(
            lambda api_key=Security(api_key_header): verify_api_key(api_key, require_full_access=False))
):
    try:
        logger.info(f"Получен запрос на сокращение URL: {url.target_url}")

        # Проверяем длину URL и обрезаем если необходимо
        original_url_str = str(url.target_url)
        max_url_length = 2048  # Максимальная длина URL в базе данных

        if len(original_url_str) > max_url_length:
            logger.warning(
                f"Длина URL превышает {max_url_length} символов (фактическая длина: {len(original_url_str)}). URL будет обрезан.")
            original_url_str = original_url_str[:max_url_length]

        # Создаем хеш URL
        url_hash = get_url_hash(original_url_str)
        logger.info(f"Создан хеш: {url_hash}")

        # Проверяем, существует ли уже активный URL с таким хешем
        existing_url = db.query(URL).filter(
            URL.url_hash == url_hash
        ).first()

        if existing_url:
            logger.info(
                f"Найдена существующая ссылка с хешем {url_hash}, код: {existing_url.short_code}, активна: {existing_url.is_active}")

            # Если ссылка неактивна, активируем её
            if not existing_url.is_active:
                logger.info(f"Активируем неактивную ссылку")
                existing_url.is_active = True
                db.commit()
                db.refresh(existing_url)

            return URLResponse(
                target_url=url.target_url,
                short_code=existing_url.short_code,
                created_at=existing_url.created_at,
                is_active=existing_url.is_active
            )

        if url.custom_code:
            logger.info(f"Запрошен пользовательский код: {url.custom_code}")
            # Проверяем, не занят ли запрошенный код активной ссылкой
            existing_code = db.query(URL).filter(
                URL.short_code == url.custom_code,
                URL.is_active == True
            ).first()

            if existing_code:
                logger.warning(f"Пользовательский код {url.custom_code} уже занят активной ссылкой")
                raise HTTPException(
                    status_code=400,
                    detail="This custom code is already taken by an active URL"
                )

            # Если код занят неактивной ссылкой, деактивируем её окончательно
            inactive_code = db.query(URL).filter(
                URL.short_code == url.custom_code,
                URL.is_active == False
            ).first()

            if inactive_code:
                logger.info(f"Найдена неактивная ссылка с кодом {url.custom_code}, удаляем её")
                db.delete(inactive_code)
                db.commit()

            short_code = url.custom_code
        else:
            logger.info("Генерируем случайный код")
            # Генерируем уникальный код
            while True:
                short_code = create_random_code()
                logger.debug(f"Сгенерирован код: {short_code}")
                # Проверяем, не существует ли уже активный код
                exists = db.query(URL).filter(
                    URL.short_code == short_code,
                    URL.is_active == True
                ).first()
                if not exists:
                    # Если код занят неактивной ссылкой, удаляем её
                    inactive_code = db.query(URL).filter(
                        URL.short_code == short_code,
                        URL.is_active == False
                    ).first()
                    if inactive_code:
                        logger.info(f"Найдена неактивная ссылка с кодом {short_code}, удаляем её")
                        db.delete(inactive_code)
                        db.commit()
                    break

        logger.info(f"Создаем новую запись в БД с кодом {short_code}")
        # Создаем новую запись в БД
        try:
            db_url = URL(
                original_url=original_url_str,  # Используем обрезанный URL если необходимо
                url_hash=url_hash,
                short_code=short_code,
                created_at=datetime.now().isoformat(),
                is_active=True
            )
            db.add(db_url)
            db.commit()
            db.refresh(db_url)
            logger.info(f"Запись успешно создана в БД")
        except IntegrityError as db_error:
            db.rollback()
            logger.error(f"Ошибка уникальности при создании short_code или url_hash: {str(db_error)}")
            raise HTTPException(status_code=400, detail="Короткий код уже существует или этот URL уже добавлен ранее")
        except Exception as db_error:
            logger.error(f"Ошибка при работе с БД: {str(db_error)}")
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(db_error)}")

        return URLResponse(
            target_url=url.target_url,  # Возвращаем исходный URL
            short_code=short_code,
            created_at=db_url.created_at,
            is_active=db_url.is_active
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Ошибка при обработке URL {url.target_url}: {str(e)}")
        # Перехватываем все исключения и возвращаем более информативную ошибку
        raise HTTPException(
            status_code=500,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )


@app.get("/{short_code}")
async def redirect_to_url(short_code: str, db: Session = Depends(get_db)):
    db_url = db.query(URL).filter(URL.short_code == short_code).first()
    if db_url is None or not db_url.is_active:
        raise HTTPException(status_code=404, detail="URL not found")

    return RedirectResponse(url=db_url.original_url, status_code=302)


@app.get("/api/test")
async def test_api_key(authenticated: bool = Depends(verify_api_key)):
    return {"message": "API key is valid"}


@app.put("/urls/{short_code}", response_model=URLResponse)
async def update_url(
        short_code: str,
        url_update: URLUpdate,
        db: Session = Depends(get_db),
        authenticated: bool = Depends(verify_api_key)
):
    # Проверяем существование URL
    db_url = db.query(URL).filter(URL.short_code == short_code).first()
    if not db_url:
        raise HTTPException(status_code=404, detail="URL not found")

    # Обновляем поля, если они предоставлены
    if url_update.target_url is not None:
        # Проверяем доступность нового URL
        if not verify_url(str(url_update.target_url)):
            raise HTTPException(
                status_code=400,
                detail="New URL is not accessible or invalid"
            )
        db_url.original_url = str(url_update.target_url)
        db_url.url_hash = get_url_hash(str(url_update.target_url))

    if url_update.short_code is not None:
        # Проверяем, не занят ли новый код
        existing_code = db.query(URL).filter(
            URL.short_code == url_update.short_code,
            URL.id != db_url.id  # Исключаем текущий URL из проверки
        ).first()

        if existing_code and existing_code.is_active:
            raise HTTPException(
                status_code=400,
                detail="This short code is already taken by an active URL"
            )

        # Если код занят неактивной ссылкой, удаляем её
        if existing_code:
            db.delete(existing_code)
            db.commit()

        db_url.short_code = url_update.short_code

    if url_update.is_active is not None:
        db_url.is_active = url_update.is_active

    try:
        db.commit()
        db.refresh(db_url)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Could not update URL: {str(e)}"
        )

    return URLResponse(
        target_url=db_url.original_url,
        short_code=db_url.short_code,
        created_at=db_url.created_at,
        is_active=db_url.is_active
    )


@app.delete("/urls/{short_code}")
async def delete_url(
        short_code: str,
        db: Session = Depends(get_db),
        authenticated: bool = Depends(verify_api_key)
):
    # Проверяем существование URL
    db_url = db.query(URL).filter(URL.short_code == short_code).first()
    if not db_url:
        raise HTTPException(status_code=404, detail="URL not found")

    # Помечаем URL как неактивный вместо физического удаления
    db_url.is_active = False
    db.commit()

    return {"message": "URL successfully deactivated"}


@app.put("/domains/{domain_id}", response_model=DomainResponse)
async def update_domain(
        domain_id: int,
        domain_update: DomainUpdate,
        db: Session = Depends(get_db),
        authenticated: bool = Depends(verify_api_key)
):
    # Проверяем существование домена
    db_domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not db_domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    # Обновляем поля, если они предоставлены
    if domain_update.redirect_url is not None:
        db_domain.redirect_url = str(domain_update.redirect_url)

    if domain_update.is_active is not None:
        db_domain.is_active = domain_update.is_active

    db.commit()
    db.refresh(db_domain)

    return DomainResponse(
        domain=db_domain.domain,
        redirect_url=db_domain.redirect_url,
        id=db_domain.id,
        created_at=db_domain.created_at,
        is_active=db_domain.is_active
    )
