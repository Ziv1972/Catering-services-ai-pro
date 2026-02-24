"""
Test fixtures - in-memory SQLite database + authenticated HTTP client
"""
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.database import Base, get_db
from backend.main import app
from backend.api.auth import get_password_hash, create_access_token
from backend.models.user import User
from backend.models.site import Site


@pytest_asyncio.fixture()
async def db_session():
    """Create a fresh in-memory SQLite database for each test"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture()
async def seed_data(db_session):
    """Insert baseline test data: user + 2 sites"""
    user = User(
        email="test@hp.com",
        full_name="Test User",
        hashed_password=get_password_hash("testpass123"),
        is_admin=True,
    )
    nz = Site(name="Nes Ziona", code="NZ", monthly_budget=60000)
    kg = Site(name="Kiryat Gat", code="KG", monthly_budget=60000)

    db_session.add_all([user, nz, kg])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(nz)
    await db_session.refresh(kg)

    return {"user": user, "nz": nz, "kg": kg}


@pytest_asyncio.fixture()
async def client(db_session, seed_data):
    """Authenticated httpx AsyncClient bound to the FastAPI app"""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token(data={"sub": seed_data["user"].email})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def unauth_client(db_session):
    """Unauthenticated httpx AsyncClient"""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as ac:
        yield ac

    app.dependency_overrides.clear()
