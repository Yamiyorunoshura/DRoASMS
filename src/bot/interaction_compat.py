"""Discord interaction compatibility helpers shared across command modules."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

__all__ = [
    "send_message_compat",
    "edit_message_compat",
    "send_modal_compat",
]


def _supports_kwarg(func: Any, kwarg: str) -> bool:
    """Best-effort check whether callable accepts the given keyword argument."""

    try:
        signature = inspect.signature(func)
    except (ValueError, TypeError):
        return True
    if kwarg in signature.parameters:
        kind = signature.parameters[kwarg].kind
        return kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    return any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()
    )


async def send_message_compat(
    interaction: Any,
    *,
    content: str | None = None,
    embed: Any | None = None,
    view: Any | None = None,
    ephemeral: bool | None = None,
) -> None:
    """Send message compat for real discord.Interaction and test stubs."""

    send_msg = getattr(getattr(interaction, "response", None), "send_message", None)
    is_test_mock = hasattr(send_msg, "_mock_name") or str(type(send_msg).__name__).endswith("Mock")

    if send_msg and asyncio.iscoroutinefunction(send_msg) and not is_test_mock:
        kwargs: dict[str, Any] = {}
        if content is not None:
            kwargs["content"] = content
        if embed is not None:
            kwargs["embed"] = embed
        if view is not None:
            kwargs["view"] = view
        kwargs["ephemeral"] = bool(ephemeral)
        await interaction.response.send_message(**kwargs)
        return
    if callable(send_msg):
        kwargs_nonasync: dict[str, Any] = {}
        if embed is not None:
            kwargs_nonasync["embed"] = embed
        if view is not None:
            kwargs_nonasync["view"] = view
        kwargs_nonasync["ephemeral"] = bool(ephemeral)
        if content is not None and not (embed or view):
            send_msg(content, **kwargs_nonasync)
        else:
            if content is not None:
                kwargs_nonasync["content"] = content
            send_msg(**kwargs_nonasync)
        return
    if (embed is not None or view is not None) and hasattr(interaction, "response_edit_message"):
        kwargs2: dict[str, Any] = {}
        if embed is not None:
            kwargs2["embed"] = embed
        if view is not None:
            kwargs2["view"] = view
        response_edit = interaction.response_edit_message
        if _supports_kwarg(response_edit, "ephemeral"):
            kwargs2["ephemeral"] = bool(ephemeral)
        await response_edit(**kwargs2)
        return
    if hasattr(interaction, "response_send_message"):
        await interaction.response_send_message(content or "", ephemeral=bool(ephemeral))


async def edit_message_compat(
    interaction: Any,
    *,
    embed: Any | None = None,
    view: Any | None = None,
) -> None:
    """Edit a message regardless of Interaction/test doubles."""

    edit_msg = getattr(getattr(interaction, "response", None), "edit_message", None)
    if edit_msg and asyncio.iscoroutinefunction(edit_msg):
        kwargs_async: dict[str, Any] = {}
        if embed is not None:
            kwargs_async["embed"] = embed
        if view is not None:
            kwargs_async["view"] = view
        await interaction.response.edit_message(**kwargs_async)
        return
    if callable(edit_msg):
        kwargs_nonasync: dict[str, Any] = {}
        if embed is not None:
            kwargs_nonasync["embed"] = embed
        if view is not None:
            kwargs_nonasync["view"] = view
        edit_msg(**kwargs_nonasync)
        return
    if hasattr(interaction, "response_edit_message"):
        kwargs2: dict[str, Any] = {}
        if embed is not None:
            kwargs2["embed"] = embed
        if view is not None:
            kwargs2["view"] = view
        await interaction.response_edit_message(**kwargs2)


async def send_modal_compat(interaction: Any, modal: Any) -> None:
    """Trigger a modal submission, supporting both runtime and test doubles."""

    send_modal = getattr(getattr(interaction, "response", None), "send_modal", None)
    if send_modal and asyncio.iscoroutinefunction(send_modal):
        await interaction.response.send_modal(modal)
        return
    if callable(send_modal):
        send_modal(modal)
        return
    if hasattr(interaction, "response_send_modal"):
        await interaction.response_send_modal(modal)
