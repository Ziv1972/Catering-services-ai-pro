"""
Database setup script
"""
import asyncio
from backend.database import engine, Base
from backend.models.user import User
from backend.models.site import Site
from backend.models.meeting import Meeting
from backend.api.auth import get_password_hash
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def setup_database():
    """Create tables and seed initial data"""
    print("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created")

    # Seed data
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession)
    async with AsyncSessionLocal() as session:
        # Create admin user
        admin = User(
            email="ziv@hp.com",
            full_name="Ziv Cohen",
            hashed_password=get_password_hash("admin123"),
            is_admin=True
        )
        session.add(admin)

        # Create sites
        nes_ziona = Site(
            name="Nes Ziona",
            code="NZ",
            monthly_budget=60000.0
        )
        kiryat_gat = Site(
            name="Kiryat Gat",
            code="KG",
            monthly_budget=60000.0
        )
        session.add_all([nes_ziona, kiryat_gat])

        await session.commit()
        print("Seed data created")

    print("\nDatabase setup complete!")
    print("\nDefault login:")
    print("  Email: ziv@hp.com")
    print("  Password: admin123")


if __name__ == "__main__":
    asyncio.run(setup_database())
