from __future__ import annotations

import pytest

from src.bot.commands import council


class _DummyTree:
    def __init__(self) -> None:
        self.client = object()
        self.commands: list[object] = []

    def add_command(self, cmd: object) -> None:
        self.commands.append(cmd)


@pytest.mark.unit
def test_register_without_container_injects_permission_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """確保非 DI 路徑能正確注入 PermissionService 依賴。"""

    captured: dict[str, object] = {}

    class DummyPermissionService:
        def __init__(
            self,
            *,
            council_service: object,
            state_council_service: object,
            supreme_assembly_service: object,
        ) -> None:
            captured["council_service"] = council_service
            captured["state_council_service"] = state_council_service
            captured["supreme_assembly_service"] = supreme_assembly_service

    class DummyCouncilServiceResult:
        def __init__(self) -> None:  # pragma: no cover - trivial
            pass

    dummy_group = object()

    monkeypatch.setattr(council, "PermissionService", DummyPermissionService)
    monkeypatch.setattr(council, "CouncilServiceResult", DummyCouncilServiceResult)
    monkeypatch.setattr(council, "build_council_group", lambda *args, **kwargs: dummy_group)
    monkeypatch.setattr(council, "_install_background_scheduler", lambda *args, **kwargs: None)

    tree = _DummyTree()
    provided_council = object()
    provided_state = object()
    provided_supreme = object()

    council.register(
        tree,
        council_service=provided_council,
        state_council_service=provided_state,
        supreme_assembly_service=provided_supreme,
    )

    assert tree.commands == [dummy_group]
    assert captured["council_service"] is not None
    assert captured["state_council_service"] is provided_state
    assert captured["supreme_assembly_service"] is provided_supreme
