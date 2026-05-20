"""Unit tests for provider-specific exception classes.

Tests that ``ProviderNotSupportedError``, ``ProviderAuthError``,
and ``ProviderApiError`` can be imported, instantiated, carry
expected attributes, and have meaningful string representations.
"""

from tinycua_sdk.core.exceptions import ProviderApiError, ProviderAuthError, ProviderNotSupportedError


class TestProviderNotSupportedError:
    """ProviderNotSupportedError behavior."""

    def test_instantiation(self) -> None:
        exc = ProviderNotSupportedError("unknown-provider", ["openai", "openai-compatible"])
        assert exc.provider_id == "unknown-provider"
        assert exc.supported_list == ["openai", "openai-compatible"]

    def test_string_representation(self) -> None:
        exc = ProviderNotSupportedError("bad", ["good"])
        msg = str(exc)
        assert "bad" in msg
        assert "good" in msg

    def test_string_representation_no_supported(self) -> None:
        exc = ProviderNotSupportedError("unknown")
        msg = str(exc)
        assert "unknown" in msg

    def test_is_value_error_subclass(self) -> None:
        exc = ProviderNotSupportedError("test", ["a"])
        assert isinstance(exc, ValueError)

    def test_pickling(self) -> None:
        import pickle

        exc = ProviderNotSupportedError("xyz", ["a", "b"])
        reconstructed = pickle.loads(pickle.dumps(exc))
        assert reconstructed.provider_id == "xyz"
        assert reconstructed.supported_list == ["a", "b"]


class TestProviderAuthError:
    """ProviderAuthError behavior."""

    def test_instantiation(self) -> None:
        exc = ProviderAuthError("Invalid API key")
        assert exc.message == "Invalid API key"

    def test_string_representation(self) -> None:
        exc = ProviderAuthError("Auth failed")
        assert "Auth failed" in str(exc)

    def test_is_exception_subclass(self) -> None:
        exc = ProviderAuthError("test")
        assert isinstance(exc, Exception)


class TestProviderApiError:
    """ProviderApiError behavior."""

    def test_instantiation(self) -> None:
        exc = ProviderApiError(429, "Rate limit exceeded")
        assert exc.status_code == 429
        assert exc.message == "Rate limit exceeded"

    def test_string_representation_includes_status(self) -> None:
        exc = ProviderApiError(401, "Unauthorized")
        msg = str(exc)
        assert "401" in msg
        assert "Unauthorized" in msg

    def test_is_exception_subclass(self) -> None:
        exc = ProviderApiError(500, "Server error")
        assert isinstance(exc, Exception)

    def test_pickling(self) -> None:
        import pickle

        exc = ProviderApiError(503, "Service unavailable")
        reconstructed = pickle.loads(pickle.dumps(exc))
        assert reconstructed.status_code == 503
        assert reconstructed.message == "Service unavailable"
