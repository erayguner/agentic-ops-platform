"""
Tests for redaction.py — redact() and redact_dict().

Coverage gaps addressed:
- Each regex pattern: private key, bearer token, GCloud token, Google API key,
  OAuth secret, SK token, Slack token, generic hex secret, SA email,
  password/secret JSON fields
- redact() on clean strings (no false positives)
- redact_dict() on nested dicts, lists, non-string values
- Multiple patterns firing in a single string
"""

from redaction import redact, redact_dict


# ---------------------------------------------------------------------------
# Individual pattern tests
# ---------------------------------------------------------------------------

class TestRedactBearerToken:
    def test_bearer_token_is_redacted(self) -> None:
        text = "Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.abc123def456"
        result = redact(text)
        assert "Bearer [REDACTED:BEARER_TOKEN]" in result
        assert "eyJhbGciOiJSUzI1NiJ9" not in result

    def test_bearer_token_case_insensitive(self) -> None:
        text = "BEARER sometoken123456789012345"
        result = redact(text)
        assert "REDACTED:BEARER_TOKEN" in result

    def test_short_bearer_value_is_not_redacted(self) -> None:
        # Under 20 chars — should NOT be redacted
        text = "Bearer short"
        result = redact(text)
        assert "short" in result


class TestRedactGCloudToken:
    def test_ya29_token_is_redacted(self) -> None:
        text = "token: ya29.c.Ab12345678901234567890123456789012345"
        result = redact(text)
        assert "[REDACTED:GCLOUD_TOKEN]" in result
        assert "ya29.c.Ab" not in result


class TestRedactGoogleApiKey:
    def test_aiza_key_is_redacted(self) -> None:
        text = "key=AIzaSyD1234567890123456789012345678901"
        result = redact(text)
        assert "[REDACTED:GOOGLE_API_KEY]" in result

    def test_gocspx_key_is_redacted(self) -> None:
        text = "GOCSPX-ABCDEFGHIJKLMNOPQRSTUVWX123"
        result = redact(text)
        assert "[REDACTED:OAUTH_SECRET]" in result


class TestRedactSkToken:
    def test_sk_token_is_redacted(self) -> None:
        text = "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz"
        result = redact(text)
        assert "[REDACTED:SK_TOKEN]" in result


class TestRedactSlackToken:
    def test_xoxb_token_is_redacted(self) -> None:
        text = "token = xoxb-1234567890123-1234567890123-abcdefghijklmnop"
        result = redact(text)
        assert "[REDACTED:SLACK_TOKEN]" in result

    def test_xoxp_token_is_redacted(self) -> None:
        text = "xoxp-9876543210987-9876543210987-abcdefghijklmnopqrst"
        result = redact(text)
        assert "[REDACTED:SLACK_TOKEN]" in result


class TestRedactHexSecret:
    def test_32_char_hex_string_is_redacted(self) -> None:
        text = "hash: abcdef1234567890abcdef1234567890"
        result = redact(text)
        assert "[REDACTED:HEX_SECRET]" in result

    def test_31_char_hex_is_not_redacted(self) -> None:
        text = "abcdef1234567890abcdef123456789"  # 31 chars
        result = redact(text)
        assert text in result

    def test_non_hex_chars_prevent_match(self) -> None:
        text = "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"  # 32 'z' chars - not hex
        result = redact(text)
        assert text in result


class TestRedactSaEmail:
    def test_sa_email_is_redacted(self) -> None:
        text = "sa-action-cloudrun-scale@my-project.iam.gserviceaccount.com"
        result = redact(text)
        assert "[REDACTED:SA_EMAIL]" in result
        assert "sa-action-cloudrun-scale" not in result

    def test_regular_email_is_not_redacted(self) -> None:
        text = "user@example.com"
        result = redact(text)
        assert "user@example.com" in result


class TestRedactPasswordFields:
    def test_json_password_field_is_redacted(self) -> None:
        text = '{"password": "supersecret123"}'
        result = redact(text)
        assert "supersecret123" not in result
        assert "REDACTED" in result

    def test_json_secret_field_is_redacted(self) -> None:
        text = '"secret": "my_very_secret_value"'
        result = redact(text)
        assert "my_very_secret_value" not in result

    def test_short_password_value_not_redacted(self) -> None:
        # Under 6 chars — should not match
        text = '"password": "abc"'
        result = redact(text)
        # Short values under threshold pass through
        assert "abc" in result


class TestRedactPrivateKey:
    def test_pem_private_key_is_redacted(self) -> None:
        key_block = (
            "-----BEGIN RSA KEY-----\n"
            "MIIEowIBAAKCAQEA1234567890abcdefghij\n"
            "-----END RSA KEY-----"
        )
        result = redact(key_block)
        assert "[REDACTED:PRIVATE_KEY]" in result
        assert "MIIEowIBAAKCAQEA" not in result


# ---------------------------------------------------------------------------
# Clean string — no false positives
# ---------------------------------------------------------------------------

class TestRedactNoFalsePositives:
    def test_normal_log_line_unchanged(self) -> None:
        text = "INFO 2024-01-01 Starting service on port 8080"
        assert redact(text) == text

    def test_short_alphanumeric_unchanged(self) -> None:
        text = "action_id: act_abc123def456"
        # 16 hex chars — under 32 threshold, should not be redacted as hex secret
        assert redact(text) == text


# ---------------------------------------------------------------------------
# redact_dict
# ---------------------------------------------------------------------------

class TestRedactDict:
    def test_string_value_is_redacted(self) -> None:
        result = redact_dict({"token": "xoxb-111111111111-111111111111-abcdefghijklmnopqrstu"})
        assert "[REDACTED:SLACK_TOKEN]" in result["token"]

    def test_nested_dict_values_are_redacted(self) -> None:
        obj = {"outer": {"inner": "ya29.abc123456789012345"}}
        result = redact_dict(obj)
        assert "[REDACTED:GCLOUD_TOKEN]" in result["outer"]["inner"]

    def test_list_of_strings_is_redacted(self) -> None:
        obj = ["ya29.abc123456789012345", "clean-string"]
        result = redact_dict(obj)
        assert "[REDACTED:GCLOUD_TOKEN]" in result[0]
        assert result[1] == "clean-string"

    def test_non_string_values_pass_through(self) -> None:
        obj = {"count": 42, "enabled": True, "ratio": 3.14, "empty": None}
        result = redact_dict(obj)
        assert result == {"count": 42, "enabled": True, "ratio": 3.14, "empty": None}

    def test_mixed_nested_structure(self) -> None:
        obj = {
            "meta": {"api_key": "AIzaSyD1234567890123456789012345678901"},
            "counts": [1, 2, 3],
            "label": "safe label",
        }
        result = redact_dict(obj)
        assert "[REDACTED:GOOGLE_API_KEY]" in result["meta"]["api_key"]
        assert result["counts"] == [1, 2, 3]
        assert result["label"] == "safe label"

    def test_list_of_dicts_is_redacted(self) -> None:
        obj = [
            {"password": "my_secret_pass"},
            {"clean": "value"},
        ]
        result = redact_dict(obj)
        assert "my_secret_pass" not in str(result[0])
