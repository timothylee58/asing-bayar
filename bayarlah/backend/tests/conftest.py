import os

# Set required env vars before any app imports so Settings() validates
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")

import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_supabase, get_redis, get_current_user

# UUIDs must be v4: pos 12 = "4", pos 16 in [89ab]
FAKE_USER_ID = "a0000000-0000-4000-8000-000000000001"
FAKE_BILL_ID = "a0000000-0000-4000-8000-000000000002"
FAKE_PARTICIPANT_ID = "a0000000-0000-4000-8000-000000000003"
FAKE_PAYMENT_ID = "a0000000-0000-4000-8000-000000000004"
FAKE_PARTICIPANT_ID_2 = "a0000000-0000-4000-8000-000000000005"


def _build_supabase_mock():
    """Return a MagicMock supabase client where all chain methods return the same
    chain object so tests can override `.execute.return_value.data` per test."""
    chain = MagicMock()
    result = MagicMock()
    result.data = []
    chain.execute.return_value = result
    chain.eq.return_value = chain
    chain.in_.return_value = chain
    chain.order.return_value = chain
    chain.single.return_value = chain
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    sb = MagicMock()
    sb.table.return_value = chain

    storage_bucket = MagicMock()
    storage_bucket.upload.return_value = MagicMock(data={"path": "test.jpg"}, error=None)
    storage_bucket.get_public_url.return_value = (
        "https://test.supabase.co/storage/v1/object/public/receipts/test.jpg"
    )
    sb.storage = MagicMock()
    sb.storage.from_.return_value = storage_bucket

    return sb


@pytest.fixture
def fake_user():
    user = MagicMock()
    user.id = FAKE_USER_ID
    return user


@pytest.fixture
def mock_supabase():
    return _build_supabase_mock()


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.exists = AsyncMock(return_value=0)
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock(return_value=True)
    return r


@pytest.fixture
def client(fake_user, mock_supabase, mock_redis):
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    app.dependency_overrides[get_redis] = lambda: mock_redis
    app.dependency_overrides[get_current_user] = lambda: fake_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
