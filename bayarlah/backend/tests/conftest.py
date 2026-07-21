"""
Pytest configuration.

Stubs out third-party packages that need external services (Supabase / Redis)
before any app module imports them.  The stubs are thin MagicMocks — enough
for models, pure-function, and health-endpoint tests to run without a live
database or broker.

In CI, the same stubs apply; no real Supabase or Redis connection is made
during the test suite.
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
# We stub unconditionally so the test suite never touches the real supabase
# C-extension chain (cryptography ← jwt ← gotrue ← supabase), which may panic
# in containers where _cffi_backend is missing.

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
