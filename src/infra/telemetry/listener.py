from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Awaitable, Callable
from inspect import iscoroutinefunction
from typing import Any, cast
from uuid import UUID

import structlog

from src.db import pool as db_pool
from src.db.gateway.economy_queries import EconomyQueryGateway
from src.db.gateway.state_council_governance import StateCouncilGovernanceGateway
from src.infra.events.state_council_events import (
    StateCouncilEvent,
)
from src.infra.events.state_council_events import (
    publish as publish_state_council_event,
)
from src.infra.types.db import ConnectionProtocol, PoolProtocol

LOGGER = structlog.get_logger(__name__)
NotificationHandler = Callable[[str], Awaitable[None] | None]


class TelemetryListener:
    """Background listener for PostgreSQL NOTIFY events."""

    def __init__(
        self,
        *,
        channel: str = "economy_events",
        handler: NotificationHandler | None = None,
        transfer_coordinator: Any | None = None,
        discord_client: Any | None = None,
    ) -> None:
        self._channel = channel
        self._handler = handler or self._default_handler
        self._transfer_coordinator = transfer_coordinator
        self._discord_client = discord_client
        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None
        # 最近處理過的交易/互動 Token，用於去重，以免重複通知
        self._seen_tx: set[str] = set()
        self._tx_order: deque[str] = deque(maxlen=10000)
        self._seen_tokens: set[str] = set()
        self._token_order: deque[str] = deque(maxlen=10000)

    async def start(self) -> None:
        """Begin listening for NOTIFY events."""
        if self._task is not None and not self._task.done():
            return

        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="telemetry-listener")
        LOGGER.info("telemetry.listener.started", channel=self._channel)

    async def stop(self) -> None:
        """Signal the listener to stop and wait for shutdown."""
        if self._task is None:
            return

        if self._stop_event is not None:
            self._stop_event.set()

        try:
            await self._task
        finally:
            self._task = None
            self._stop_event = None
            LOGGER.info("telemetry.listener.stopped", channel=self._channel)

    async def _run(self) -> None:
        try:
            pool = await db_pool.init_pool()
            # 在部分環境中 asyncpg 缺少完整型別資訊；以 Any/Dynamic 呼叫即可。
            async with cast(Any, pool).acquire() as connection:
                await connection.add_listener(self._channel, self._dispatch)

                try:
                    if self._stop_event is None:
                        self._stop_event = asyncio.Event()

                    await self._stop_event.wait()
                finally:
                    await connection.remove_listener(self._channel, self._dispatch)
        except Exception:
            LOGGER.exception("telemetry.listener.error")
            raise

    async def _dispatch(
        self,
        connection: Any,
        pid: int,
        channel: str,
        payload: str,
    ) -> None:
        del connection, pid, channel
        result = self._handler(payload)
        if asyncio.iscoroutine(result):
            await result

    async def _default_handler(self, payload: str) -> None:
        """Default observer: parse JSON payloads and emit structured logs."""
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            LOGGER.warning(
                "telemetry.listener.payload.unparseable",
                payload=payload,
            )
            return

        if not isinstance(parsed, dict):
            LOGGER.info(
                "telemetry.listener.payload.raw",
                payload=payload,
            )
            return

        # 之後流程使用具體型別以減少 Unknown 診斷
        from typing import cast as _cast

        data = _cast(dict[str, Any], parsed)
        event_type = data.get("event_type", "unknown")
        if event_type == "transaction_success":
            tx_id_raw = data.get("transaction_id")
            tx_id: str | None = None
            if isinstance(tx_id_raw, str):
                tx_id = tx_id_raw
            elif isinstance(tx_id_raw, dict):
                txd: dict[str, Any] = _cast(dict[str, Any], tx_id_raw)
                hexval = txd.get("hex")
                if isinstance(hexval, str):
                    tx_id = hexval

            LOGGER.info(
                "telemetry.transfer.success",
                guild_id=data.get("guild_id"),
                initiator_id=data.get("initiator_id"),
                target_id=data.get("target_id"),
                amount=data.get("amount"),
                metadata=data.get("metadata", {}),
            )
            # 轉帳成功時通知接收者（私訊）
            try:
                # 若同一 transaction_id 已處理，略過 DM（去重）
                if tx_id is None or not self._is_tx_seen(tx_id):
                    await self._notify_target_dm(data)
            except Exception:
                LOGGER.exception("telemetry.listener.notify_target_failed", payload=data)
            # 轉帳成功時通知發起人（伺服器內 ephemeral notification）
            try:
                await self._notify_initiator_server(data)
            except Exception:
                LOGGER.exception("telemetry.listener.notify_initiator_server_failed", payload=data)
            # 嘗試判定是否涉及政府部門帳戶，若是則通知國務院面板刷新
            await _maybe_emit_state_council_event(data, cause="transaction_success")
        elif event_type == "transaction_denied":
            LOGGER.warning(
                "telemetry.transfer.denied",
                guild_id=data.get("guild_id"),
                initiator_id=data.get("initiator_id"),
                reason=data.get("reason"),
                metadata=data.get("metadata", {}),
            )
            # 轉帳失敗時通知發起人（私訊）
            try:
                await self._notify_initiator_dm(data)
            except Exception:
                LOGGER.exception("telemetry.listener.notify_initiator_failed", payload=data)
        elif event_type == "adjustment_success":
            LOGGER.info(
                "telemetry.adjustment.success",
                guild_id=data.get("guild_id"),
                admin_id=data.get("admin_id"),
                target_id=data.get("target_id"),
                amount=data.get("amount"),
                direction=data.get("direction"),
                reason=data.get("reason"),
                metadata=data.get("metadata", {}),
            )
            await _maybe_emit_state_council_event(data, cause="adjustment_success")
        elif event_type == "transfer_check_result":
            # Handle transfer check result events
            await self._handle_transfer_check_result(data)
        elif event_type == "transfer_check_approved":
            # Handle transfer check approved events
            await self._handle_transfer_check_approved(data)
        else:
            LOGGER.info("telemetry.listener.payload.received", payload=data)

    async def _notify_target_dm(self, parsed: Any) -> None:
        """以 DM 通知轉帳成功的接收者。

        僅在有提供 discord_client 時啟用，若找不到使用者則靜默略過。
        政府帳戶（理事會或部門帳戶）不會收到通知。
        """
        if self._discord_client is None:
            return

        initiator_id = parsed.get("initiator_id")
        target_id = parsed.get("target_id")
        amount = parsed.get("amount")
        metadata = parsed.get("metadata", {})
        if isinstance(metadata, dict):
            from typing import cast as _cast

            meta = _cast(dict[str, Any], metadata)
            _rv = meta.get("reason")
            reason: str | None = _rv if isinstance(_rv, str) else None
        else:
            reason = None

        try:
            uid = int(target_id)
        except Exception:
            return

        # 跳過政府帳戶（理事會帳戶：9e15+，部門帳戶：9.5e15+）
        # 這些是虛擬帳戶，不是真實的 Discord 用戶
        if uid >= 9_000_000_000_000_000:
            return

        user = None
        try:
            getter = getattr(self._discord_client, "get_user", None)
            if callable(getter):
                user = getter(uid)
            if user is None and hasattr(self._discord_client, "fetch_user"):
                user = await self._discord_client.fetch_user(uid)
        except Exception:
            user = None

        if user is None:
            return

        try:
            if isinstance(initiator_id, int):
                initiator_display = f"<@{initiator_id}>"
            elif isinstance(initiator_id, str) and initiator_id.isdigit():
                initiator_display = f"<@{int(initiator_id)}>"
            else:
                initiator_display = "發送者"
        except Exception:
            initiator_display = "發送者"

        lines = [
            f"✅ 你收到了來自 {initiator_display} 的轉帳。",
        ]
        if amount is not None:
            try:
                amt = int(amount)
                lines.append(f"💰 金額：{amt:,} 點")
            except Exception:
                pass
        if reason:
            lines.append(f"📝 備註：{reason}")

        try:
            await cast(Any, user).send("\n".join(lines))
        except Exception:
            # DM 失敗不應影響主流程
            LOGGER.debug("telemetry.listener.notify_target.dm_failed", target_id=uid)

    async def _notify_initiator_dm(self, parsed: Any) -> None:
        """以 DM 通知轉帳失敗的發起人。

        僅在有提供 discord_client 時啟用，若找不到使用者則靜默略過。
        """
        if self._discord_client is None:
            return

        initiator_id = parsed.get("initiator_id")
        target_id = parsed.get("target_id")
        amount = parsed.get("amount")
        reason = parsed.get("reason") or "transfer_failed"

        try:
            uid = int(initiator_id)
        except Exception:
            return

        user = None
        try:
            getter = getattr(self._discord_client, "get_user", None)
            if callable(getter):
                user = getter(uid)
            if user is None and hasattr(self._discord_client, "fetch_user"):
                user = await self._discord_client.fetch_user(uid)
        except Exception:
            user = None

        if user is None:
            return

        try:
            if isinstance(target_id, int):
                target_display = f"<@{target_id}>"
            elif isinstance(target_id, str) and target_id.isdigit():
                target_display = f"<@{int(target_id)}>"
            else:
                target_display = "對方"
        except Exception:
            target_display = "對方"

        lines = [
            "❌ 你的轉帳請求未通過檢查，已被取消。",
            f"📋 事由：{reason}",
        ]
        if amount is not None:
            try:
                amt = int(amount)
                lines.append(f"金額：{amt:,} 點 → {target_display}")
            except Exception:
                pass

        try:
            await cast(Any, user).send("\n".join(lines))
        except Exception:
            # DM 失敗不應影響主流程
            LOGGER.debug("telemetry.listener.notify_initiator.dm_failed", initiator_id=uid)

    async def _notify_initiator_server(self, parsed: Any) -> None:
        """以伺服器內 ephemeral notification 通知轉帳成功的發起人。

        僅在有提供 discord_client 且 metadata 中包含 interaction_token 時啟用。
        使用 Discord HTTP API 發送 interaction followup。
        若 token 過期或發送失敗，靜默略過（不影響轉帳流程）。
        """
        if self._discord_client is None:
            return

        metadata = parsed.get("metadata", {})
        if not isinstance(metadata, dict):
            return
        from typing import cast as _cast

        metadata = _cast(dict[str, Any], metadata)

        token_raw = metadata.get("interaction_token")
        interaction_token: str | None = token_raw if isinstance(token_raw, str) else None
        if not interaction_token:
            # 同步模式下沒有 token，跳過
            return

        # 同一 interaction_token 只發一次（去重）
        if self._is_token_seen(str(interaction_token)):
            return

        guild_id = parsed.get("guild_id")
        initiator_id = parsed.get("initiator_id")
        target_id = parsed.get("target_id")
        amount = parsed.get("amount")
        reason_val = metadata.get("reason")
        reason: str | None = reason_val if isinstance(reason_val, str) else None

        try:
            application_id = getattr(self._discord_client, "application_id", None)
            if not application_id:
                LOGGER.debug(
                    "telemetry.listener.notify_initiator_server.no_application_id",
                    guild_id=guild_id,
                )
                return

            # 格式化收款人資訊
            try:
                if isinstance(target_id, int):
                    target_display = f"<@{target_id}>"
                elif isinstance(target_id, str) and target_id.isdigit():
                    target_display = f"<@{int(target_id)}>"
                else:
                    target_display = "收款人"
            except Exception:
                target_display = "收款人"

            # 查詢轉帳後的餘額（僅讀取，避免 fn_get_balance 造成鎖等待）
            initiator_balance = None
            try:
                pool = db_pool.get_pool()
            except RuntimeError:
                pool = None

            if pool is not None and guild_id is not None and initiator_id is not None:
                try:
                    economy = EconomyQueryGateway()
                    async with cast(Any, pool).acquire() as conn:
                        balance_result = None

                        snapshot_fetcher = getattr(economy, "fetch_balance_snapshot", None)
                        if snapshot_fetcher and iscoroutinefunction(snapshot_fetcher):
                            balance_result = await snapshot_fetcher(
                                conn, guild_id=guild_id, member_id=initiator_id
                            )
                        else:
                            balance_fetcher = getattr(economy, "fetch_balance", None)
                            if balance_fetcher and iscoroutinefunction(balance_fetcher):
                                balance_result = await balance_fetcher(
                                    conn, guild_id=guild_id, member_id=initiator_id
                                )

                    if balance_result is not None:
                        initiator_balance = balance_result.balance
                except Exception:
                    # 查詢餘額失敗不影響通知發送
                    LOGGER.debug(
                        "telemetry.listener.notify_initiator_server.balance_query_failed",
                        guild_id=guild_id,
                        initiator_id=initiator_id,
                    )

            # 格式化訊息
            lines: list[str] = []
            if amount is not None:
                try:
                    amt = int(amount)
                    lines.append(f"✅ 已成功將 {amt:,} 點轉給 {target_display}。")
                except Exception:
                    lines.append("✅ 轉帳成功。")
            else:
                lines.append("✅ 轉帳成功。")

            if initiator_balance is not None:
                lines.append(f"👉 你目前的餘額為 {initiator_balance:,} 點。")

            if reason:
                lines.append(f"📝 備註：{reason}")

            content = "\n".join(lines)

            # 使用 Discord HTTP API 發送 followup
            # EPHEMERAL flag = 64
            # Discord API endpoint: POST /webhooks/{application_id}/{interaction_token}
            from discord.http import Route

            route = Route(
                "POST",
                "/webhooks/{application_id}/{interaction_token}",
                application_id=application_id,
                interaction_token=interaction_token,
            )
            await self._discord_client.http.request(
                route,
                json={"content": content, "flags": 64},
            )

            LOGGER.debug(
                "telemetry.listener.notify_initiator_server.sent",
                guild_id=guild_id,
                initiator_id=initiator_id,
            )
        except Exception:
            # 通知失敗不應影響主流程（token 可能過期、guild 不存在等）
            LOGGER.debug(
                "telemetry.listener.notify_initiator_server.failed",
                guild_id=guild_id,
                initiator_id=initiator_id,
                exc_info=True,
            )

    def _is_tx_seen(self, tx: str) -> bool:
        if tx in self._seen_tx:
            return True
        self._seen_tx.add(tx)
        self._tx_order.append(tx)
        # deque 自動淘汰最舊項；維持 set 大小一致
        while len(self._seen_tx) > len(self._tx_order):
            oldest = self._tx_order[0] if self._tx_order else None
            if oldest and oldest in self._seen_tx:
                self._seen_tx.discard(oldest)
            break
        return False

    def _is_token_seen(self, token: str) -> bool:
        if token in self._seen_tokens:
            return True
        self._seen_tokens.add(token)
        self._token_order.append(token)
        while len(self._seen_tokens) > len(self._token_order):
            oldest = self._token_order[0] if self._token_order else None
            if oldest and oldest in self._seen_tokens:
                self._seen_tokens.discard(oldest)
            break
        return False

    async def _handle_transfer_check_result(self, parsed: Any) -> None:
        """Handle transfer check result event."""
        if self._transfer_coordinator is None:
            return

        try:
            transfer_id_str = parsed.get("transfer_id")
            if not transfer_id_str:
                return

            transfer_id = (
                UUID(transfer_id_str) if isinstance(transfer_id_str, str) else transfer_id_str
            )
            check_type = parsed.get("check_type")
            result = parsed.get("result")

            if check_type and result is not None:
                await self._transfer_coordinator.handle_check_result(
                    transfer_id=transfer_id,
                    check_type=check_type,
                    result=int(result),
                )
        except Exception:
            LOGGER.exception("telemetry.listener.transfer_check_result.error", payload=parsed)

    async def _handle_transfer_check_approved(self, parsed: Any) -> None:
        """Handle transfer check approved event."""
        if self._transfer_coordinator is None:
            return

        try:
            transfer_id_str = parsed.get("transfer_id")
            if not transfer_id_str:
                return

            transfer_id = (
                UUID(transfer_id_str) if isinstance(transfer_id_str, str) else transfer_id_str
            )
            await self._transfer_coordinator.handle_check_approved(transfer_id=transfer_id)
        except Exception:
            LOGGER.exception("telemetry.listener.transfer_check_approved.error", payload=parsed)


async def _maybe_emit_state_council_event(parsed: Any, *, cause: str) -> None:
    """若經濟事件涉及政府部門帳戶，發布國務院事件以觸發面板更新。

    - transfer：initiator/target 其中任一為政府帳戶
    - adjustment：target 為政府帳戶
    任何命中都發出 `department_balance_changed`。
    """
    try:
        guild_id = int(parsed.get("guild_id"))
    except Exception:
        return

    initiator_id = parsed.get("initiator_id")
    target_id = parsed.get("target_id")

    try:
        pool = cast(PoolProtocol, db_pool.get_pool())
        governance = StateCouncilGovernanceGateway()
        economy = EconomyQueryGateway()
        # 型別提示：PoolProtocol.acquire() 會回傳 AsyncContextManager[ConnectionProtocol]
        async with pool.acquire() as conn:
            # 在嚴格模式下，部分第三方庫的回傳型別較寬鬆；此處直接標註以協助型別推論
            conn_typed: ConnectionProtocol = conn
            accounts = await governance.fetch_government_accounts(conn_typed, guild_id=guild_id)
            if not accounts:
                return

            id_to_dept = {acc.account_id: acc.department for acc in accounts}

            # 判定受影響部門
            affected_ids: set[int] = set()
            if isinstance(initiator_id, int) and initiator_id in id_to_dept:
                affected_ids.add(int(initiator_id))
            if isinstance(target_id, int) and target_id in id_to_dept:
                affected_ids.add(int(target_id))

            if not affected_ids:
                return

            # 與經濟帳本對齊治理層餘額（最佳努力、單連線）
            for acc in accounts:
                if acc.account_id not in affected_ids:
                    continue
                try:
                    snap = await economy.fetch_balance(
                        conn_typed, guild_id=guild_id, member_id=acc.account_id
                    )
                    await governance.update_account_balance(
                        conn_typed, account_id=acc.account_id, new_balance=snap.balance
                    )
                except Exception:
                    # 設計上不讓 listener 失敗阻斷事件，失敗時略過同步
                    LOGGER.debug(
                        "telemetry.listener.sync_failed",
                        guild_id=guild_id,
                        account_id=acc.account_id,
                        department=acc.department,
                        cause=cause,
                    )

            affected_depts = tuple(sorted({id_to_dept[aid] for aid in affected_ids}))

            await publish_state_council_event(
                StateCouncilEvent(
                    guild_id=guild_id,
                    kind="department_balance_changed",
                    departments=affected_depts,
                    cause=cause,
                )
            )
    except Exception:  # pragma: no cover - 防禦性處理避免中斷 listener
        LOGGER.warning(
            "telemetry.listener.state_council.emit_failed",
            guild_id=parsed.get("guild_id"),
            cause=cause,
        )
