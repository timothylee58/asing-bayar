"""
Pytest configuration.

Stubs out third-party packages that need external services (Supabase / Redis)
before any app module imports them, then provides fixtures that swap the app's
database and cache dependencies for the in-memory fakes in tests/fakes.py.

No test touches a real Supabase or Redis.
"""
import os
import sys
from unittest.mock import MagicMock

# ── Environment ──────────────────────────────────────────────────────────────
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

# ── Supabase / gotrue stubs ──────────────────────────────────────────────────
# Stubbed unconditionally so the suite never touches the real supabase C-extension
# chain (cryptography <- jwt <- gotrue <- supabase), which can panic in containers
# where _cffi_backend is missing. `postgrest` stays real: the fakes raise its APIError.
_mock_client = MagicMock()
_supabase_mod = MagicMock()
_supabase_mod.Client = MagicMock
_supabase_mod.create_client = MagicMock(return_value=_mock_client)

for _name in [
    "supabase",
    "supabase._async",
    "supabase._async.auth_client",
    "supabase._sync",
    "supabase._sync.auth_client",
    "gotrue",
    "gotrue.errors",
    "gotrue._async",
    "gotrue._async.gotrue_client",
    "gotrue._sync",
    "gotrue._sync.gotrue_client",
]:
    sys.modules[_name] = MagicMock()

sys.modules["supabase"] = _supabase_mod

# ── Redis async stub ─────────────────────────────────────────────────────────
_redis_mod = MagicMock()
_redis_mod.Redis = MagicMock
_redis_mod.from_url = MagicMock(return_value=MagicMock())
sys.modules.setdefault("redis", MagicMock())
sys.modules.setdefault("redis.asyncio", _redis_mod)

# Imported after the stubs above are installed.
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.dependencies import get_redis, get_supabase  # noqa: E402
from app.main import app  # noqa: E402
from tests.fakes import FakeDB, FakeRedis  # noqa: E402

# ── Stable ids (valid UUID4s, as the request models require) ─────────────────
FAKE_USER_ID = "22222222-2222-4222-8222-222222222222"
OTHER_USER_ID = "99999999-9999-4999-8999-999999999999"
FAKE_BILL_ID = "11111111-1111-4111-8111-111111111111"
FAKE_PARTICIPANT_ID = "33333333-3333-4333-8333-333333333333"
FAKE_PARTICIPANT_ID_2 = "44444444-4444-4444-8444-444444444444"
FAKE_PAYMENT_ID = "55555555-5555-4555-8555-555555555555"
MISSING_ID = "00000000-0000-4000-8000-000000000000"


@pytest.fixture(autouse=True)
def _reset_singletons():
    """The app caches one Redis pool / Supabase client per process. Never let one
    test's instance (or stub) leak into the next."""
    from app.core import dependencies

    dependencies._redis = None
    dependencies._supabase_client.cache_clear()
    yield
    dependencies._redis = None
    dependencies._supabase_client.cache_clear()


@pytest.fixture
def db() -> FakeDB:
    return FakeDB()


@pytest.fixture
def redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def client(db, redis):
    app.dependency_overrides[get_supabase] = lambda: db
    app.dependency_overrides[get_redis] = lambda: redis
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def organiser(db):
    """Auth headers for the bill organiser (signed in via the fake Supabase Auth)."""
    return db.add_user(FAKE_USER_ID)


@pytest.fixture
def stranger(db):
    """Auth headers for a different signed-in user who owns nothing."""
    return db.add_user(OTHER_USER_ID)


@pytest.fixture
def world(db, organiser):
    """A bill (RM60, three participants of RM20) owned by FAKE_USER_ID."""
    return db.seed_bill(FAKE_USER_ID)
