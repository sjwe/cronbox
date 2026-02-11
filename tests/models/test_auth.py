from cronbox.models.auth import (
    generate_api_key,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_password_and_verify(self):
        pw = "my-secure-password"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed)

    def test_verify_wrong_password(self):
        hashed = hash_password("correct-password")
        assert not verify_password("wrong-password", hashed)


class TestAPIKeyGeneration:
    def test_generate_api_key_format(self):
        full_key, prefix, key_hash = generate_api_key()
        assert full_key.startswith("cb_")
        assert prefix == full_key[:12]
        assert len(key_hash) == 64  # SHA-256 hex

    def test_api_key_hash_deterministic(self):
        import hashlib

        full_key, _, key_hash = generate_api_key()
        expected = hashlib.sha256(full_key.encode()).hexdigest()
        assert key_hash == expected
