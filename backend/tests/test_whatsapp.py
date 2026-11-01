import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def test_whatsapp_status_endpoint(client: TestClient):
    """GET /api/whatsapp/status returns configuration status."""
    res = client.get("/api/whatsapp/status")
    assert res.status_code == 200
    data = res.json()
    assert "configured" in data
    assert "api_version" in data
    assert data["api_version"] == "v18.0"


def test_whatsapp_preview_reorder(client: TestClient):
    """GET /api/whatsapp/preview/reorder generates draft text and click-to-chat fallback."""
    res = client.get("/api/whatsapp/preview/reorder?recipient_phone=9876543210")
    assert res.status_code == 200
    data = res.json()
    assert "message_text" in data
    assert "recipient_phone" in data
    assert data["recipient_phone"] == "919876543210"
    assert "click_to_chat_url" in data
    assert "https://wa.me/919876543210" in data["click_to_chat_url"]


def test_whatsapp_send_fallback_when_unconfigured(client: TestClient):
    """POST /api/whatsapp/send returns fallback link when token/phone_id are unconfigured."""
    payload = {
        "recipient_phone": "9876543210",
        "message_text": "Please send 10 bags of rice"
    }
    res = client.post("/api/whatsapp/send", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "fallback_url" in data
    assert "wa.me" in data["fallback_url"]


def test_whatsapp_send_with_mocked_cloud_api(client: TestClient):
    """POST /api/whatsapp/send dispatches to Meta Graph API when configured."""
    with patch("app.services.whatsapp_service.WHATSAPP_ACCESS_TOKEN", "test_meta_token_123"), \
         patch("app.services.whatsapp_service.WHATSAPP_PHONE_NUMBER_ID", "100200300400"):

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = b'{"messages": [{"id": "wamid.HBgL"}]}'
            mock_urlopen.return_value.__enter__.return_value = mock_response

            payload = {
                "recipient_phone": "9876543210",
                "message_text": "Please dispatch 20 kg sugar"
            }
            res = client.post("/api/whatsapp/send", json=payload)
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is True
            assert data["message_id"] == "wamid.HBgL"
            assert data["status"] == "accepted_by_provider"


def test_whatsapp_webhook_verification(client: TestClient):
    """GET /api/whatsapp/webhook handles Meta challenge verification."""
    with patch("app.services.whatsapp_service.WHATSAPP_VERIFY_TOKEN", "my_secret_verify_token"):
        # Correct token
        res = client.get("/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=my_secret_verify_token&hub.challenge=1158201444")
        assert res.status_code == 200
        assert res.text == "1158201444"

        # Wrong token
        res_bad = client.get("/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=wrong_token&hub.challenge=1158201444")
        assert res_bad.status_code == 403


def test_whatsapp_webhook_event_receiver(client: TestClient):
    """POST /api/whatsapp/webhook acknowledges inbound events."""
    event_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "12345",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [{"from": "919876543210", "text": {"body": "Order received!"}}]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    res = client.post("/api/whatsapp/webhook", json=event_payload)
    assert res.status_code == 200
    assert res.json() == {"status": "received"}
