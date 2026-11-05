"""Boot-time safety: refuse half-configured payment gateways; production hides docs."""
import importlib

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.services import payment_gateway
from app.services.payment_gateway import HitPayGateway, StubGateway

BASE = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_KEY": "k", "SUPABASE_ANON_KEY": "k"}


def make(**over) -> Settings:
    return Settings(_env_file=None, **{**BASE, **over})


class TestGatewayConfigValidation:
    def test_disabled_needs_nothing(self):
        make(PAYMENT_GATEWAY_ENABLED=False)

    @pytest.mark.parametrize("missing", ["HITPAY_API_KEY", "HITPAY_WEBHOOK_SALT"])
    def test_enabled_without_secrets_refuses_to_boot(self, missing):
        creds = {"HITPAY_API_KEY": "key", "HITPAY_WEBHOOK_SALT": "salt"}
        creds.pop(missing)
        with pytest.raises(ValidationError, match=missing):
            make(PAYMENT_GATEWAY_ENABLED=True, **creds)

    def test_production_refuses_sandbox_mode(self):
        with pytest.raises(ValidationError, match="HITPAY_SANDBOX"):
            make(ENV="production", PAYMENT_GATEWAY_ENABLED=True, HITPAY_API_KEY="k", HITPAY_WEBHOOK_SALT="s",
                 HITPAY_SANDBOX=True, BACKEND_PUBLIC_URL="https://api.example.my")

    def test_production_needs_a_real_webhook_origin(self):
        with pytest.raises(ValidationError, match="BACKEND_PUBLIC_URL"):
            make(ENV="production", PAYMENT_GATEWAY_ENABLED=True, HITPAY_API_KEY="k", HITPAY_WEBHOOK_SALT="s",
                 HITPAY_SANDBOX=False)

    def test_a_correct_production_config_boots(self):
        s = make(ENV="production", PAYMENT_GATEWAY_ENABLED=True, HITPAY_API_KEY="k", HITPAY_WEBHOOK_SALT="s",
                 HITPAY_SANDBOX=False, BACKEND_PUBLIC_URL="https://api.example.my")
        assert s.is_production

    def test_unrelated_env_vars_do_not_break_loading(self):
        make(SOMETHING_ELSE="ignored")


class TestGatewayFactory:
    def test_disabled_gives_the_stub(self, monkeypatch):
        monkeypatch.setattr(settings, "PAYMENT_GATEWAY_ENABLED", False)
        assert isinstance(payment_gateway.get_gateway(), StubGateway)

    def test_enabled_gives_the_real_gateway(self, monkeypatch):
        monkeypatch.setattr(settings, "PAYMENT_GATEWAY_ENABLED", True)
        monkeypatch.setattr(settings, "HITPAY_API_KEY", "k")
        assert isinstance(payment_gateway.get_gateway(), HitPayGateway)

    def test_enabled_but_keyless_is_an_error_not_a_silent_stub(self, monkeypatch):
        """The stub accepts unsigned webhooks, so falling back to it would be fail-open."""
        monkeypatch.setattr(settings, "PAYMENT_GATEWAY_ENABLED", True)
        monkeypatch.setattr(settings, "HITPAY_API_KEY", "")
        with pytest.raises(RuntimeError):
            payment_gateway.get_gateway()

    def test_unsupported_provider_is_an_error(self, monkeypatch):
        monkeypatch.setattr(settings, "PAYMENT_GATEWAY_ENABLED", True)
        monkeypatch.setattr(settings, "PAYMENT_GATEWAY_PROVIDER", "stripe")
        with pytest.raises(RuntimeError, match="stripe"):
            payment_gateway.get_gateway()


def test_production_serves_no_docs_or_schema(monkeypatch):
    import app.main as main

    monkeypatch.setattr(settings, "ENV", "production")
    prod = importlib.reload(main)
    try:
        c = TestClient(prod.app)
        assert c.get("/docs").status_code == 404
        assert c.get("/openapi.json").status_code == 404
    finally:
        monkeypatch.setattr(settings, "ENV", "development")
        importlib.reload(main)


class TestCors:
    def preflight(self, client, origin, method="POST"):
        return client.options("/api/payments/confirm", headers={
            "Origin": origin, "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "authorization,content-type"})

    def test_allowed_origin_may_send_credentials_headers(self, client):
        res = self.preflight(client, "http://localhost:3000")
        assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_other_origins_are_not_allowed(self, client):
        assert "access-control-allow-origin" not in self.preflight(client, "https://evil.example").headers

    def test_methods_are_limited(self, client):
        assert self.preflight(client, "http://localhost:3000", "PUT").status_code == 400


def test_health_reveals_nothing_but_liveness(client):
    assert client.get("/health").json() == {"status": "ok"}
