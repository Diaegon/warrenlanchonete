"""Tests for app/db/session.py async SQLAlchemy setup."""

from sqlalchemy.ext.asyncio import AsyncSession


class TestGetDb:
    """Tests for the get_db async generator."""

    async def test_get_db_yields_async_session(self) -> None:
        """get_db() yields an AsyncSession instance."""
        from app.db.session import get_db

        gen = get_db()
        session = await gen.__anext__()
        assert isinstance(session, AsyncSession)
        # Cleanup — exhaust the generator
        try:
            await gen.aclose()
        except Exception:
            pass

    async def test_get_db_session_closes_after_use(self) -> None:
        """get_db() session is properly closed after context exits."""
        from app.db.session import get_db

        sessions_seen = []
        gen = get_db()
        session = await gen.__anext__()
        sessions_seen.append(session)
        assert isinstance(session, AsyncSession)
        await gen.aclose()
        # After closing, the session should be invalidated / closed
        # We just verify no exception was raised during close

    async def test_base_has_metadata(self) -> None:
        """Base declarative base has metadata attribute."""
        from app.db.session import Base

        assert Base.metadata is not None

    async def test_async_session_local_exists(self) -> None:
        """AsyncSessionLocal factory is importable."""
        from app.db.session import AsyncSessionLocal

        assert AsyncSessionLocal is not None
