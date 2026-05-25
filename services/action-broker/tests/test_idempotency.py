"""
Tests for idempotency.py — _make_key and IdempotencyStore.

Coverage gaps addressed:
- _make_key determinism and sensitivity to each input component
- IdempotencyStore.check in dry-run and live mode
- IdempotencyStore.record in dry-run and live mode
- None Firestore client handling (graceful no-op)
- LIVE_MODE env var toggling
"""
from unittest.mock import MagicMock, patch


from idempotency import IdempotencyStore, _make_key


# ---------------------------------------------------------------------------
# _make_key
# ---------------------------------------------------------------------------

class TestMakeKey:
    def test_same_inputs_produce_same_key(self) -> None:
        k1 = _make_key("corr-1", "cloud_run.scale_within_range", {"name": "svc"})
        k2 = _make_key("corr-1", "cloud_run.scale_within_range", {"name": "svc"})
        assert k1 == k2

    def test_different_correlation_id_produces_different_key(self) -> None:
        k1 = _make_key("corr-1", "cloud_run.scale_within_range", {"name": "svc"})
        k2 = _make_key("corr-2", "cloud_run.scale_within_range", {"name": "svc"})
        assert k1 != k2

    def test_different_action_class_produces_different_key(self) -> None:
        k1 = _make_key("corr-1", "cloud_run.scale_within_range", {"name": "svc"})
        k2 = _make_key("corr-1", "iam.disable_service_account_key", {"name": "svc"})
        assert k1 != k2

    def test_different_target_produces_different_key(self) -> None:
        k1 = _make_key("corr-1", "cloud_run.scale_within_range", {"name": "svc-a"})
        k2 = _make_key("corr-1", "cloud_run.scale_within_range", {"name": "svc-b"})
        assert k1 != k2

    def test_key_is_deterministic_regardless_of_dict_insertion_order(self) -> None:
        k1 = _make_key("c", "a", {"x": 1, "y": 2})
        k2 = _make_key("c", "a", {"y": 2, "x": 1})
        assert k1 == k2

    def test_key_is_a_64_char_hex_string(self) -> None:
        k = _make_key("corr-1", "action.class", {"foo": "bar"})
        assert len(k) == 64
        assert all(c in "0123456789abcdef" for c in k)


# ---------------------------------------------------------------------------
# IdempotencyStore.check
# ---------------------------------------------------------------------------

class TestIdempotencyStoreCheck:
    def test_check_in_dry_run_always_returns_none(self) -> None:
        store = IdempotencyStore(firestore_client=None)
        with patch.dict("os.environ", {"LIVE_MODE": "false"}):
            result = store.check("c1", "action", {"k": "v"})
        assert result is None

    def test_check_with_none_client_in_live_mode_returns_none(self) -> None:
        store = IdempotencyStore(firestore_client=None)
        with patch.dict("os.environ", {"LIVE_MODE": "true"}):
            result = store.check("c1", "action", {"k": "v"})
        assert result is None

    def test_check_hit_returns_stored_outcome(self) -> None:
        stored = {"status": "success", "detail": "scaled"}
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = stored

        mock_client = MagicMock()
        mock_client.collection.return_value.document.return_value.get.return_value = mock_doc

        store = IdempotencyStore(firestore_client=mock_client)
        with patch("idempotency.LIVE_MODE", True):
            result = store.check("c1", "action", {"k": "v"})

        assert result == stored

    def test_check_miss_returns_none(self) -> None:
        mock_doc = MagicMock()
        mock_doc.exists = False

        mock_client = MagicMock()
        mock_client.collection.return_value.document.return_value.get.return_value = mock_doc

        store = IdempotencyStore(firestore_client=mock_client)
        with patch("idempotency.LIVE_MODE", True):
            result = store.check("c1", "action", {"k": "v"})

        assert result is None

    def test_check_uses_correct_collection_name(self) -> None:
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_client = MagicMock()
        mock_client.collection.return_value.document.return_value.get.return_value = mock_doc

        store = IdempotencyStore(firestore_client=mock_client)
        with patch("idempotency.LIVE_MODE", True):
            store.check("c1", "action", {})

        mock_client.collection.assert_called_once_with("aop_idempotency_keys")


# ---------------------------------------------------------------------------
# IdempotencyStore.record
# ---------------------------------------------------------------------------

class TestIdempotencyStoreRecord:
    def test_record_in_dry_run_does_not_call_firestore(self) -> None:
        mock_client = MagicMock()
        store = IdempotencyStore(firestore_client=mock_client)

        with patch.dict("os.environ", {"LIVE_MODE": "false"}):
            store.record("c1", "action", {"k": "v"}, {"status": "ok"})

        mock_client.collection.assert_not_called()

    def test_record_with_none_client_in_live_mode_is_noop(self) -> None:
        store = IdempotencyStore(firestore_client=None)
        with patch("idempotency.LIVE_MODE", True):
            # Should not raise
            store.record("c1", "action", {"k": "v"}, {"status": "ok"})

    def test_record_in_live_mode_calls_set_on_firestore(self) -> None:
        mock_client = MagicMock()
        store = IdempotencyStore(firestore_client=mock_client)

        with patch("idempotency.LIVE_MODE", True):
            store.record("c1", "action", {"k": "v"}, {"status": "ok"})

        mock_client.collection.return_value.document.return_value.set.assert_called_once()

    def test_record_payload_contains_required_fields(self) -> None:
        captured = {}

        def fake_set(data):
            captured.update(data)

        mock_doc = MagicMock()
        mock_doc.set = fake_set
        mock_client = MagicMock()
        mock_client.collection.return_value.document.return_value = mock_doc

        store = IdempotencyStore(firestore_client=mock_client)
        outcome = {"status": "success"}
        with patch("idempotency.LIVE_MODE", True):
            store.record("corr-1", "my.action", {"name": "svc"}, outcome)

        assert captured.get("correlation_id") == "corr-1"
        assert captured.get("action_class") == "my.action"
        assert captured.get("outcome") == outcome
        assert "recorded_at" in captured
