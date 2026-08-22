# conftest.py
# Shared fixtures: isolated data directory, fake clock, session seeder.

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from perido import database, timer


class FakeClock:
    """Callable replacement for perido.timer.now with manual control."""

    def __init__(self, start: datetime) -> None:
        self._t = start

    def __call__(self) -> datetime:
        return self._t

    def advance(self, **kwargs: float) -> None:
        """Move the clock forward by a timedelta keyword (minutes=...)."""
        self._t += timedelta(**kwargs)

    def set(self, value: datetime) -> None:
        """Move the clock to an absolute instant."""
        self._t = value


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Redirect all storage into a temporary PERIDO_HOME."""
    monkeypatch.setenv("PERIDO_HOME", str(tmp_path / "data"))
    return tmp_path / "data"


@pytest.fixture
def clock(monkeypatch):
    """Patch the global clock to a fixed, manually advanced fake."""
    fake = FakeClock(datetime(2026, 8, 20, 14, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(timer, "now", fake)
    return fake


@pytest.fixture
def day_clock(monkeypatch):
    """Fake clock anchored at local noon so day maths never straddles
    midnight regardless of the machine's timezone."""
    noon = datetime.now().astimezone().replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    fake = FakeClock(noon.astimezone(timezone.utc))
    monkeypatch.setattr(timer, "now", fake)
    return fake


@pytest.fixture
def seed(clock):
    """Return a factory that inserts finished sessions directly."""

    def _seed(
        *,
        kind: str = "focus",
        minutes: float = 25,
        status: str = "completed",
        days_ago: int = 0,
        hour: int | None = None,
        actual_seconds: float | None = None,
        extension_minutes: float = 0,
        cycle_name: str | None = None,
        cycle_position: int | None = None,
    ) -> dict:
        start = clock() - timedelta(days=days_ago)
        if hour is not None:
            local = start.astimezone().replace(
                hour=hour, minute=0, second=0, microsecond=0
            )
            start = local.astimezone(timezone.utc)
        conn = database.connect()
        try:
            session = database.create_session(
                conn,
                kind=kind,
                minutes=minutes + extension_minutes,
                start=start,
                cycle_name=cycle_name,
                cycle_position=cycle_position,
            )
            if status != "active":
                actual = (
                    minutes * 60 if actual_seconds is None else actual_seconds
                )
                database.update_session(
                    conn,
                    session["id"],
                    status=status,
                    actual_seconds=actual,
                    extension_minutes=extension_minutes,
                )
            return database.get_session(conn, session["id"])
        finally:
            conn.close()

    return _seed
