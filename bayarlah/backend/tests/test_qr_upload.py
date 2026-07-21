"""Tests for the DuitNow QR image upload endpoint.

POST /api/bills/{bill_id}/payment-qr
"""
import io
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

BILL_ID = str(uuid4())
ORGANISER_ID = str(uuid4())
OTHER_USER_ID = str(uuid4())


def _make_image_file(size_kb: int = 50, filename: str = "qr.png", content_type: str = "image/png"):
    """Create a fake image file for testing."""
    data = b"\x89PNG\r\n" + b"\x00" * (size_kb * 1024)
    return ("file", (filename, io.BytesIO(data), content_type))


def _mock_auth_user(user_id: str):
    """Create a mock user object for auth dependency."""
    user = MagicMock()
    user.id = user_id
    return user


def _override_deps(user_id: str = ORGANISER_ID, bill_exists: bool = True, bill_organiser: str = ORGANISER_ID):
    """Override dependencies with mocks."""
    mock_supabase = MagicMock()
    mock_user = _mock_auth_user(user_id)

    # Bill lookup
    if bill_exists:
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data={"organiser_id": bill_organiser, "payment_details": {}}
        )
    else:
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=None
        )

    # Storage mock
    mock_bucket = MagicMock()
    mock_bucket.get_public_url.return_value = f"https://test.supabase.co/storage/v1/object/public/payment-qr/{BILL_ID}.png"
    mock_supabase.storage.from_.return_value = mock_bucket

    # Update mock
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

    from app.core.dependencies import get_supabase, get_current_user
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    app.dependency_overrides[get_current_user] = lambda: mock_user

    return mock_supabase, mock_bucket


def _cleanup_deps():
    app.dependency_overrides.clear()


class TestQRUploadHappyPath:
    def setup_method(self):
        self.mock_supabase, self.mock_bucket = _override_deps()

    def teardown_method(self):
        _cleanup_deps()

    def test_upload_png_success(self):
        """Organiser uploads a PNG QR image successfully."""
        res = client.post(
            f"/api/bills/{BILL_ID}/payment-qr",
            files=[_make_image_file(size_kb=50, filename="duitnow-qr.png")],
        )
        assert res.status_code == 200
        data = res.json()
        assert "duitnow_qr_url" in data
        assert BILL_ID in data["duitnow_qr_url"]
        assert data["duitnow_qr_url"].endswith(".png")

    def test_upload_jpg_success(self):
        """JPEG files should also be accepted."""
        res = client.post(
            f"/api/bills/{BILL_ID}/payment-qr",
            files=[_make_image_file(size_kb=100, filename="qr.jpg", content_type="image/jpeg")],
        )
        assert res.status_code == 200
        data = res.json()
        assert "duitnow_qr_url" in data

    def test_storage_upload_called(self):
        """Verify the file is uploaded to Supabase Storage."""
        client.post(
            f"/api/bills/{BILL_ID}/payment-qr",
            files=[_make_image_file()],
        )
        self.mock_bucket.upload.assert_called_once()
        call_args = self.mock_bucket.upload.call_args
        assert f"payment-qr/{BILL_ID}" in call_args[0][0]

    def test_payment_details_updated(self):
        """Verify payment_details JSONB is updated with the QR URL."""
        client.post(
            f"/api/bills/{BILL_ID}/payment-qr",
            files=[_make_image_file()],
        )
        # The update call should contain the QR URL
        update_call = self.mock_supabase.table.return_value.update
        update_call.assert_called()
        update_args = update_call.call_args[0][0]
        assert "payment_details" in update_args
        assert "duitnow_qr_url" in update_args["payment_details"]


class TestQRUploadValidation:
    def setup_method(self):
        self.mock_supabase, self.mock_bucket = _override_deps()

    def teardown_method(self):
        _cleanup_deps()

    def test_non_image_rejected(self):
        """Non-image files (PDF, text, etc.) should be rejected with 422."""
        res = client.post(
            f"/api/bills/{BILL_ID}/payment-qr",
            files=[("file", ("doc.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf"))],
        )
        assert res.status_code == 422
        assert "image" in res.json()["detail"].lower()

    def test_oversized_file_rejected(self):
        """Files over 3MB should be rejected."""
        # Create a 4MB file
        large_data = b"\x89PNG\r\n" + b"\x00" * (4 * 1024 * 1024)
        res = client.post(
            f"/api/bills/{BILL_ID}/payment-qr",
            files=[("file", ("large.png", io.BytesIO(large_data), "image/png"))],
        )
        assert res.status_code == 422
        assert "3MB" in res.json()["detail"] or "under" in res.json()["detail"].lower()

    def test_no_file_returns_422(self):
        """Request without file should return 422."""
        res = client.post(f"/api/bills/{BILL_ID}/payment-qr")
        assert res.status_code == 422


class TestQRUploadAuthorization:
    def teardown_method(self):
        _cleanup_deps()

    def test_non_organiser_rejected(self):
        """Only the bill organiser can upload QR images."""
        _override_deps(user_id=OTHER_USER_ID, bill_organiser=ORGANISER_ID)
        res = client.post(
            f"/api/bills/{BILL_ID}/payment-qr",
            files=[_make_image_file()],
        )
        assert res.status_code == 403
        assert "organiser" in res.json()["detail"].lower()

    def test_bill_not_found(self):
        """Uploading to a non-existent bill returns 404."""
        _override_deps(bill_exists=False)
        res = client.post(
            f"/api/bills/{uuid4()}/payment-qr",
            files=[_make_image_file()],
        )
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()


class TestQRUploadRouteRegistration:
    def test_route_exists(self):
        """POST /api/bills/{id}/payment-qr should not return 404 or 405."""
        res = client.post(
            f"/api/bills/{uuid4()}/payment-qr",
            files=[_make_image_file()],
        )
        # Should get 401 (no auth) or another error, but NOT 404/405
        assert res.status_code not in (404, 405)
