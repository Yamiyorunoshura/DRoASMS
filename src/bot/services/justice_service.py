from __future__ import annotations

from types import TracebackType
from typing import Any, Sequence, cast

import structlog

from src.cython_ext.state_council_models import Suspect
from src.db.gateway.justice_governance import JusticeGovernanceGateway
from src.db.gateway.state_council_governance import StateCouncilGovernanceGateway
from src.db.pool import get_pool
from src.infra.types.db import ConnectionProtocol, PoolProtocol

LOGGER = structlog.get_logger(__name__)


class _AcquireConnectionContext:
    """Async context manager wrapper for pool.acquire() results."""

    def __init__(self, pool_obj: Any, acq_obj: Any) -> None:
        self._pool = pool_obj
        self._acq = acq_obj
        self._conn: Any | None = None

    async def __aenter__(self) -> ConnectionProtocol:
        self._conn = await self._acq.__aenter__()
        return cast(ConnectionProtocol, self._conn)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._conn:
            await self._acq.__aexit__(exc_type, exc_val, exc_tb)


class JusticeService:
    """Service for managing justice department operations."""

    def __init__(
        self,
        *,
        gateway: JusticeGovernanceGateway | None = None,
        state_council_gateway: StateCouncilGovernanceGateway | None = None,
    ) -> None:
        self._gateway = gateway or JusticeGovernanceGateway()
        self._state_council_gateway = state_council_gateway or StateCouncilGovernanceGateway()

    async def _pool_acquire_cm(self, pool: PoolProtocol) -> _AcquireConnectionContext:
        """Get a connection context manager from the pool."""
        acq = pool.acquire()
        return _AcquireConnectionContext(pool, acq)

    async def create_suspect_on_arrest(
        self,
        *,
        guild_id: int,
        member_id: int,
        arrested_by: int,
        arrest_reason: str,
    ) -> Suspect:
        """Create a suspect record when someone is arrested by homeland security."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        cm = await self._pool_acquire_cm(pool)
        async with cm as conn:
            # Check if there's already an active suspect record
            existing = await self._gateway.get_suspect_by_member(
                conn,
                guild_id=guild_id,
                member_id=member_id,
            )

            if existing:
                LOGGER.warning(
                    "justice_service.create_suspect_already_exists",
                    guild_id=guild_id,
                    member_id=member_id,
                    existing_suspect_id=str(existing.id),
                )
                return existing

            suspect = await self._gateway.create_suspect(
                conn,
                guild_id=guild_id,
                member_id=member_id,
                arrested_by=arrested_by,
                arrest_reason=arrest_reason,
            )

            LOGGER.info(
                "justice_service.suspect_created",
                guild_id=guild_id,
                suspect_id=str(suspect.id),
                member_id=member_id,
                arrested_by=arrested_by,
            )

            return suspect

    async def get_active_suspects(
        self,
        *,
        guild_id: int,
        page: int = 1,
        page_size: int = 10,
        status: str | None = None,
    ) -> tuple[Sequence[Suspect], int]:
        """取得嫌犯列表（支援狀態篩選與分頁）。

        Args:
            guild_id: 公會 ID
            page: 頁碼（從 1 開始）
            page_size: 每頁筆數
            status: 可選單一狀態過濾；若為 ``None`` 則預設僅包含 ``detained`` 與 ``charged``。
        """
        offset = (page - 1) * page_size
        if status is not None:
            statuses: Sequence[str] = (status,)
        else:
            statuses = ("detained", "charged")

        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        cm = await self._pool_acquire_cm(pool)
        async with cm as conn:
            suspects = await self._gateway.get_active_suspects(
                conn,
                guild_id=guild_id,
                statuses=statuses,
                limit=page_size,
                offset=offset,
            )

            # Get total count for pagination
            count_query = """
                SELECT COUNT(*) as total
                FROM governance.suspects
                WHERE guild_id = $1 AND status = ANY($2::text[])
            """
            result = await conn.fetchrow(count_query, guild_id, list(statuses))
            total = int(result["total"]) if result and result["total"] is not None else 0

            return suspects, total

    async def get_suspects(
        self,
        *,
        guild_id: int,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[Sequence[Suspect], int]:
        """Backward-compatible別名：取得活躍嫌犯列表（含分頁資訊）。"""
        return await self.get_active_suspects(
            guild_id=guild_id,
            page=page,
            page_size=page_size,
        )

    async def charge_suspect(
        self,
        *,
        guild_id: int,
        suspect_id: int,
        justice_member_id: int,
        justice_member_roles: Sequence[int] | None = None,
    ) -> Suspect:
        """Charge a suspect (change from detained to charged)."""
        # Verify permissions - only justice department leaders can charge suspects
        if not await self._verify_justice_permissions(
            guild_id=guild_id,
            member_id=justice_member_id,
            member_roles=justice_member_roles,
        ):
            raise PermissionError("只有法務部領導人可以起訴嫌犯")

        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        cm = await self._pool_acquire_cm(pool)
        async with cm as conn:
            try:
                suspect = await self._gateway.charge_suspect(conn, suspect_id=suspect_id)
            except ValueError as exc:
                # 規格要求：嘗試對已起訴嫌犯再次起訴時，需提供明確錯誤訊息
                raise ValueError("該嫌犯已被起訴") from exc

            LOGGER.info(
                "justice_service.suspect_charged",
                guild_id=guild_id,
                suspect_id=str(suspect_id),
                charged_by=justice_member_id,
            )

            return suspect

    async def revoke_charge(
        self,
        *,
        guild_id: int,
        suspect_id: int,
        justice_member_id: int,
        justice_member_roles: Sequence[int] | None = None,
    ) -> Suspect:
        """撤銷起訴：將嫌犯狀態從 charged 改回 detained，並清空起訴時間。"""
        if not await self._verify_justice_permissions(
            guild_id=guild_id,
            member_id=justice_member_id,
            member_roles=justice_member_roles,
        ):
            raise PermissionError("只有法務部領導人可以撤銷起訴")

        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        cm = await self._pool_acquire_cm(pool)
        async with cm as conn:
            try:
                suspect = await self._gateway.revoke_charge(conn, suspect_id=suspect_id)
            except ValueError as exc:
                # 僅允許對已起訴嫌犯撤銷；其他狀態視為錯誤
                raise ValueError("該嫌犯尚未被起訴") from exc

            LOGGER.info(
                "justice_service.suspect_charge_revoked",
                guild_id=guild_id,
                suspect_id=str(suspect_id),
                revoked_by=justice_member_id,
            )

            return suspect

    async def release_suspect(
        self,
        *,
        guild_id: int,
        suspect_id: int,
        justice_member_id: int,
        justice_member_roles: Sequence[int] | None = None,
    ) -> Suspect:
        """Release a suspect (change from detained/charged to released)."""
        # Verify permissions - only justice department leaders can release charged suspects
        if not await self._verify_justice_permissions(
            guild_id=guild_id,
            member_id=justice_member_id,
            member_roles=justice_member_roles,
        ):
            raise PermissionError("只有法務部領導人可以釋放已起訴嫌犯")

        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        cm = await self._pool_acquire_cm(pool)
        async with cm as conn:
            suspect = await self._gateway.release_suspect(conn, suspect_id=suspect_id)

            LOGGER.info(
                "justice_service.suspect_released",
                guild_id=guild_id,
                suspect_id=str(suspect_id),
                released_by=justice_member_id,
            )

            return suspect

    async def mark_member_released_from_security(
        self,
        *,
        guild_id: int,
        member_id: int,
    ) -> None:
        """由國土安全部/自動機制釋放嫌犯時，更新嫌犯表狀態為 released。

        不進行額外權限檢查，僅在已有進行中記錄（detained/charged）時嘗試更新；
        若查無記錄或已為 released，則靜默略過。
        """
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        cm = await self._pool_acquire_cm(pool)
        async with cm as conn:
            suspect = await self._gateway.get_suspect_by_member(
                conn,
                guild_id=guild_id,
                member_id=member_id,
            )
            if not suspect or suspect.status == "released":
                return
            try:
                await self._gateway.release_suspect(conn, suspect_id=suspect.id)
            except ValueError:
                # 已被其他流程更新為 released 或記錄不存在時，視為已同步
                return

            LOGGER.info(
                "justice_service.suspect_released_by_security",
                guild_id=guild_id,
                member_id=member_id,
            )

    async def get_suspect_by_member(
        self,
        *,
        guild_id: int,
        member_id: int,
    ) -> Suspect | None:
        """Get active suspect record for a member."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        cm = await self._pool_acquire_cm(pool)
        async with cm as conn:
            return await self._gateway.get_suspect_by_member(
                conn,
                guild_id=guild_id,
                member_id=member_id,
            )

    async def get_member_latest_record(
        self,
        *,
        guild_id: int,
        member_id: int,
    ) -> Suspect | None:
        """取得成員最新一筆嫌犯記錄（包含 detained/charged/released）。"""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        cm = await self._pool_acquire_cm(pool)
        async with cm as conn:
            return await self._gateway.get_latest_suspect_record(
                conn,
                guild_id=guild_id,
                member_id=member_id,
            )

    async def is_member_charged(
        self,
        *,
        guild_id: int,
        member_id: int,
    ) -> bool:
        """檢查指定成員是否有『已起訴』的嫌犯記錄。"""
        suspect = await self.get_suspect_by_member(guild_id=guild_id, member_id=member_id)
        return bool(suspect and suspect.status == "charged")

    async def _verify_justice_permissions(
        self,
        *,
        guild_id: int,
        member_id: int,
        member_roles: Sequence[int] | None = None,
    ) -> bool:
        """Verify if a member has justice department leadership permissions.

        授權規則與國務院服務的部門權限檢查保持一致：
        1) 具備「法務部」部門角色的成員視為有權限；
        2) 國務院領袖（身分或角色）一律擁有全域司法權限。

        注意：實際的 Discord 身分組清單由呼叫端傳入（member_roles），
        以避免在服務層硬編碼 Discord 相依邏輯。
        """
        roles = list(member_roles or [])

        try:
            # 延遲匯入以避免模組層級循環相依
            from src.bot.services.state_council_service import StateCouncilService

            sc_service = StateCouncilService(gateway=self._state_council_gateway)

            # 1) 先檢查是否具備法務部部門權限
            try:
                if await sc_service.check_department_permission(
                    guild_id=guild_id,
                    user_id=member_id,
                    department="法務部",
                    user_roles=roles,
                ):
                    return True
            except Exception as exc:  # pragma: no cover - 防禦性日誌
                LOGGER.warning(
                    "justice_service.permission.department_check_failed",
                    guild_id=guild_id,
                    member_id=member_id,
                    error=str(exc),
                )

            # 2) 後援：國務院領袖擁有全域司法權限
            try:
                if await sc_service.check_leader_permission(
                    guild_id=guild_id,
                    user_id=member_id,
                    user_roles=roles,
                ):
                    return True
            except Exception as exc:  # pragma: no cover - 防禦性日誌
                LOGGER.warning(
                    "justice_service.permission.leader_check_failed",
                    guild_id=guild_id,
                    member_id=member_id,
                    error=str(exc),
                )

            return False

        except Exception as e:  # pragma: no cover - 防禦性日誌
            LOGGER.error(
                "justice_service.permission_check_failed",
                guild_id=guild_id,
                member_id=member_id,
                error=str(e),
            )
            return False
