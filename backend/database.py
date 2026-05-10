import os
import ssl
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base


def _build_db_url() -> tuple[str, dict]:
    """
    Normalise DATABASE_URL for asyncpg.

    Render (and most PaaS) supply a plain postgres:// or postgresql:// URL that
    may include ?sslmode=require.  asyncpg doesn't accept 'sslmode' as a keyword
    argument — it uses a Python ssl.SSLContext instead.  We strip the param and
    pass ssl=True via engine connect_args so SQLAlchemy handles it correctly.
    """
    raw = os.getenv("DATABASE_URL", "postgresql+asyncpg://tdg:tdgpass@db:5432/testdatagen")

    # 1. Fix scheme: postgres:// → postgresql+asyncpg://
    #    (Render emits 'postgres://', SQLAlchemy needs the full dialect+driver)
    if raw.startswith("postgres://"):
        raw = "postgresql+asyncpg://" + raw[len("postgres://"):]
    elif raw.startswith("postgresql://") and "+asyncpg" not in raw:
        raw = "postgresql+asyncpg://" + raw[len("postgresql://"):]

    # 2. Strip sslmode from query string and collect it
    parsed = urlparse(raw)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    sslmode = qs.pop("sslmode", [None])[0]

    # Rebuild URL without sslmode
    new_query = urlencode({k: v[0] for k, v in qs.items()})
    clean_url = urlunparse(parsed._replace(query=new_query))

    # 3. Build connect_args for asyncpg
    connect_args: dict = {}
    if sslmode and sslmode != "disable":
        # asyncpg accepts ssl=True (verify-full) or an SSLContext.
        # For Render's managed Postgres, verify-full is appropriate.
        ssl_ctx = ssl.create_default_context()
        if sslmode in ("require", "prefer"):
            # Don't verify the cert CN for self-signed Render certs
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx

    return clean_url, connect_args


DATABASE_URL, _connect_args = _build_db_url()

engine = create_async_engine(DATABASE_URL, echo=False, future=True, connect_args=_connect_args)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    from models import Session, UploadedFile, LLMSettings, GenerationJob, Profile  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
