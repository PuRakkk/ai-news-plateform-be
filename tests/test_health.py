import time
from starlette.testclient import TestClient

from app.core.cipher import SecretCipher, sign_webhook, validate_outbound_url, verify_webhook_signature
from app.core.jwt import create_access_token, decode_access_token
from app.core.security import generate_secure_otp, get_password_hash, verify_password


def test_healthz_endpoint(client: TestClient):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_auth_health_endpoint(client: TestClient):
    response = client.get("/api/v1/auth/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_jwt_token_flow():
    subject = "editor@ainews.internal"
    token = create_access_token(subject=subject)
    decoded = decode_access_token(token)
    assert decoded == subject


def test_password_hashing():
    raw_password = "SecurePassword123!"
    hashed = get_password_hash(raw_password)
    assert verify_password(raw_password, hashed)
    assert not verify_password("WrongPassword", hashed)


def test_secure_otp_generator():
    otp = generate_secure_otp(length=6)
    assert len(otp) == 6
    assert otp.isdigit()


def test_secret_cipher_encrypt_decrypt():
    cipher = SecretCipher()
    original_secret = "sk_live_very_secret_api_key_12345"
    encrypted = cipher.encrypt(original_secret)
    assert encrypted != original_secret

    decrypted = cipher.decrypt(encrypted)
    assert decrypted == original_secret


def test_webhook_signature_verification():
    secret = "whsec_test_secret_key"
    body = b'{"event":"news_approved","id":123}'
    timestamp = int(time.time())

    signature = sign_webhook(secret, timestamp, body)
    assert signature.startswith("sha256=")

    # Valid verification
    is_valid = verify_webhook_signature(secret, signature, timestamp, body)
    assert is_valid is True

    # Invalid timestamp (drift beyond 300s)
    is_valid_expired = verify_webhook_signature(secret, signature, timestamp - 400, body)
    assert is_valid_expired is False

    # Tampered body
    is_valid_tampered = verify_webhook_signature(secret, signature, timestamp, b'{"event":"hacked"}')
    assert is_valid_tampered is False


def test_ssrf_url_validation():
    # Loopback and local should be blocked
    assert validate_outbound_url("http://localhost:8080/webhook") is False
    assert validate_outbound_url("http://127.0.0.1/admin") is False
    assert validate_outbound_url("http://10.0.0.1/internal") is False
    assert validate_outbound_url("http://192.168.1.1/secret") is False

    # Valid public URL format should pass (if domain resolves)
    assert validate_outbound_url("https://example.com/webhook") is True


def test_worker_status_endpoint(client: TestClient):
    response = client.get("/api/v1/worker/status")
    assert response.status_code == 200
    data = response.json()
    assert "is_running" in data
    assert "scheduler_enabled" in data
    assert "cron_schedule" in data
    assert "redis_endpoint" in data

