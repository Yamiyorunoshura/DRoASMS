from src.config.settings import Settings


def test_settings_does_not_expose_legacy_service_result_flag() -> None:
    """Ensure unused compatibility flag is removed from Settings."""

    assert "service_result_compat_mode" not in Settings.model_fields
