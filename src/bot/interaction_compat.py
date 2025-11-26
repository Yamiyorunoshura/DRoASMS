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


def _response_already_done(interaction: Any) -> bool:
    """Best-effort check whether the interaction response was already used."""

    response = getattr(interaction, "response", None)
    if response is None:
        return False

    is_done_attr = getattr(response, "is_done", None)
    if callable(is_done_attr):
        try:
            result = is_done_attr()
        except TypeError:
            # Some stubs expose ``is_done`` as property-like attribute.
            pass
        else:
            if isinstance(result, bool):
                return result
    elif isinstance(is_done_attr, bool):  # pragma: no cover - defensive path
        return is_done_attr

    responded_flag = getattr(response, "_responded", None)
    if isinstance(responded_flag, bool):
        return responded_flag
    return False


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

    response_done = _response_already_done(interaction)
    send_msg = getattr(getattr(interaction, "response", None), "send_message", None)
    if send_msg is not None and not response_done:
        kwargs_msg: dict[str, Any] = {}
        args_msg: tuple[Any, ...] = ()
        if content is not None:
            if embed is None and view is None:
                args_msg = (content,)
            else:
                kwargs_msg["content"] = content
        if embed is not None:
            kwargs_msg["embed"] = embed
        if view is not None:
            kwargs_msg["view"] = view
        kwargs_msg["ephemeral"] = bool(ephemeral)
        result = send_msg(*args_msg, **kwargs_msg)
        if inspect.isawaitable(result):
            await result
        return
    if (
        not response_done
        and (embed is not None or view is not None)
        and hasattr(interaction, "response_edit_message")
    ):
        kwargs2: dict[str, Any] = {}
        if embed is not None:
            kwargs2["embed"] = embed
        if view is not None:
            kwargs2["view"] = view
        response_edit = interaction.response_edit_message
        if _supports_kwarg(response_edit, "ephemeral"):
            kwargs2["ephemeral"] = bool(ephemeral)
        result = response_edit(**kwargs2)
        if inspect.isawaitable(result):
            await result
        return
    if not response_done and hasattr(interaction, "response_send_message"):
        result = interaction.response_send_message(content or "", ephemeral=bool(ephemeral))
        if inspect.isawaitable(result):
            await result
        return

    followup = getattr(interaction, "followup", None)
    followup_send = getattr(followup, "send", None)
    if followup_send is not None:
        kwargs_followup: dict[str, Any] = {}
        if content is not None:
            kwargs_followup["content"] = content
        if embed is not None:
            kwargs_followup["embed"] = embed
        if view is not None:
            kwargs_followup["view"] = view
        kwargs_followup["ephemeral"] = bool(ephemeral)
        result = followup_send(**kwargs_followup)
        if inspect.isawaitable(result):
            await result
        return


async def edit_message_compat(
    interaction: Any,
    *,
    embed: Any | None = None,
    view: Any | None = None,
) -> None:
    """Edit a message regardless of Interaction/test doubles."""

    response_done = _response_already_done(interaction)
    edit_msg = getattr(getattr(interaction, "response", None), "edit_message", None)
    if edit_msg is not None and not response_done:
        kwargs_async: dict[str, Any] = {}
        if embed is not None:
            kwargs_async["embed"] = embed
        if view is not None:
            kwargs_async["view"] = view
        result = edit_msg(**kwargs_async)
        if inspect.isawaitable(result):
            await result
        return
    if not response_done and hasattr(interaction, "response_edit_message"):
        kwargs2: dict[str, Any] = {}
        if embed is not None:
            kwargs2["embed"] = embed
        if view is not None:
            kwargs2["view"] = view
        result = interaction.response_edit_message(**kwargs2)
        if inspect.isawaitable(result):
            await result
        return

    message = getattr(interaction, "message", None)
    message_edit = getattr(message, "edit", None)
    if callable(message_edit):
        kwargs_message: dict[str, Any] = {}
        if embed is not None:
            kwargs_message["embed"] = embed
        if view is not None:
            kwargs_message["view"] = view
        result = message_edit(**kwargs_message)
        if inspect.isawaitable(result):
            await result
        return

    followup = getattr(interaction, "followup", None)
    followup_edit = getattr(followup, "edit_message", None)
    if callable(followup_edit) and hasattr(interaction, "message"):
        kwargs_followup_edit: dict[str, Any] = {}
        if embed is not None:
            kwargs_followup_edit["embed"] = embed
        if view is not None:
            kwargs_followup_edit["view"] = view
        result = followup_edit(interaction.message.id, **kwargs_followup_edit)
        if inspect.isawaitable(result):
            await result
        return


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
