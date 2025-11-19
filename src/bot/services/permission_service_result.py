"""Result-based permission checking service."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Sequence, cast

import structlog

from src.infra.result import Err, Error, Ok, Result

if TYPE_CHECKING:
    from src.bot.services.council_service_result import CouncilServiceResult
    from src.bot.services.state_council_service_result import StateCouncilServiceResult
    from src.bot.services.supreme_assembly_service import SupremeAssemblyService

LOGGER = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PermissionResult:
    """權限檢查結果"""

    allowed: bool
    reason: str | None = None
    permission_level: str | None = None


class PermissionError(Error):
    """權限檢查錯誤"""


class PermissionChecker(ABC):
    """權限檢查器抽象基類"""

    @abstractmethod
    async def check_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> Result[PermissionResult, PermissionError]:
        """檢查權限並返回 Result"""
        pass


class CouncilPermissionChecker(PermissionChecker):
    """常任理事會權限檢查器（使用 Result 模式）"""

    def __init__(self, council_service: "CouncilServiceResult") -> None:
        self._council_service = council_service

    async def check_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> Result[PermissionResult, PermissionError]:
        """檢查常任理事會權限"""
        # 取得理事會設定（使用 Result 模式），失敗時轉換為 PermissionError
        config_result = await self._council_service.get_config(guild_id=guild_id)
        if isinstance(config_result, Err):
            err_obj = config_result.error
            return Err(PermissionError(f"常任理事會設定錯誤：{err_obj}"))

        cfg = getattr(config_result, "value", None)
        if cfg is None:
            return Err(PermissionError("無法取得常任理事會設定"))

        # 取得理事會身分組 ID 清單
        role_ids_result = await self._council_service.get_council_role_ids(guild_id=guild_id)
        if isinstance(role_ids_result, Err):
            err_obj = role_ids_result.error
            return Err(PermissionError(f"無法取得常任理事會身分組：{err_obj}"))

        role_ids = list(getattr(role_ids_result, "value", []))
        has_multi_role = bool(set(role_ids) & set(user_roles))
        has_single_role = bool(cfg.council_role_id and cfg.council_role_id in user_roles)

        if not (has_multi_role or has_single_role):
            return Ok(PermissionResult(allowed=False, reason="不具備常任理事身分組"))

        # 根據操作類型檢查具體權限
        match operation:
            case "panel_access":
                return Ok(PermissionResult(allowed=True, permission_level="council_member"))
            case "create_proposal":
                return Ok(PermissionResult(allowed=True, permission_level="council_member"))
            case "vote":
                return Ok(PermissionResult(allowed=True, permission_level="council_member"))
            case "cancel_proposal":
                # 提案撤案需要檢查是否為提案人
                proposer_id = kwargs.get("proposer_id")
                if proposer_id and user_id == proposer_id:
                    return Ok(PermissionResult(allowed=True, permission_level="proposal_owner"))
                return Ok(PermissionResult(allowed=False, reason="僅提案人可撤案"))
            case _:
                return Ok(PermissionResult(allowed=False, reason=f"未知的操作類型: {operation}"))


class StateCouncilPermissionChecker(PermissionChecker):
    """國務院權限檢查器（使用 Result 模式）"""

    def __init__(self, state_council_service: "StateCouncilServiceResult") -> None:
        self._state_council_service = state_council_service

    async def check_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> Result[PermissionResult, PermissionError]:
        """檢查國務院權限"""
        # Check leader permission using Result pattern
        leader_result = await self._state_council_service.check_leader_permission(
            guild_id=guild_id, user_id=user_id, user_roles=user_roles
        )
        if isinstance(leader_result, Ok) and leader_result.value:
            return Ok(PermissionResult(allowed=True, permission_level="state_council_leader"))

        # Check department permissions
        department = kwargs.get("department")
        if department:
            dept_result: Any = await self._state_council_service.check_department_permission(
                guild_id=guild_id,
                user_id=user_id,
                department_id=department,
            )
            if isinstance(dept_result, Ok) and bool(cast(Any, dept_result).value):
                return Ok(PermissionResult(allowed=True, permission_level=f"{department}_member"))

        return Ok(PermissionResult(allowed=False, reason="不具備國務院領袖或部門權限"))


class SupremeAssemblyPermissionChecker(PermissionChecker):
    """最高議會權限檢查器（使用 Result 模式）"""

    def __init__(self, assembly_service: "SupremeAssemblyService") -> None:
        self._assembly_service = assembly_service

    async def check_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> Result[PermissionResult, PermissionError]:
        """檢查最高議會權限"""
        # 判斷使用者是否為最高議會成員：目前以 member_role_id 是否出現在 user_roles 為準
        try:
            cfg = await self._assembly_service.get_config(guild_id=guild_id)
        except Exception as exc:
            LOGGER.error("supreme_assembly.permission.get_config_failed", error=str(exc))
            return Err(PermissionError("最高議會設定錯誤"))

        if cfg.member_role_id not in user_roles:
            return Ok(PermissionResult(allowed=False, reason="非最高議會成員"))

        # 根據操作類型檢查具體權限
        match operation:
            case "panel_access":
                return Ok(PermissionResult(allowed=True, permission_level="assembly_member"))
            case "vote":
                return Ok(PermissionResult(allowed=True, permission_level="assembly_member"))
            case _:
                return Ok(PermissionResult(allowed=False, reason=f"未知的操作類型: {operation}"))


class PermissionService:
    """統一權限檢查服務（使用 Result 模式）"""

    def __init__(
        self,
        *,
        council_service: CouncilServiceResult | None = None,
        state_council_service: StateCouncilServiceResult | None = None,
        supreme_assembly_service: SupremeAssemblyService | None = None,
    ) -> None:
        self._checkers: dict[str, PermissionChecker] = {}

        if council_service is not None:
            self._checkers["council"] = CouncilPermissionChecker(council_service)
        if state_council_service is not None:
            self._checkers["state_council"] = StateCouncilPermissionChecker(state_council_service)
        if supreme_assembly_service is not None:
            self._checkers["supreme_assembly"] = SupremeAssemblyPermissionChecker(
                supreme_assembly_service
            )

    async def check_council_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str = "panel_access",
        **kwargs: Any,
    ) -> Result[PermissionResult, PermissionError]:
        """檢查常任理事會權限"""
        checker = self._checkers.get("council")
        if checker is None:
            return Err(PermissionError("常任理事會服務未初始化"))

        return await checker.check_permission(
            guild_id=guild_id,
            user_id=user_id,
            user_roles=user_roles,
            operation=operation,
            **kwargs,
        )

    async def check_state_council_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str = "panel_access",
        **kwargs: Any,
    ) -> Result[PermissionResult, PermissionError]:
        """檢查國務院權限"""
        checker = self._checkers.get("state_council")
        if checker is None:
            return Err(PermissionError("國務院服務未初始化"))

        return await checker.check_permission(
            guild_id=guild_id,
            user_id=user_id,
            user_roles=user_roles,
            operation=operation,
            **kwargs,
        )

    async def check_supreme_assembly_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str = "panel_access",
        **kwargs: Any,
    ) -> Result[PermissionResult, PermissionError]:
        """檢查最高議會權限"""
        checker = self._checkers.get("supreme_assembly")
        if checker is None:
            return Err(PermissionError("最高議會服務未初始化"))

        return await checker.check_permission(
            guild_id=guild_id,
            user_id=user_id,
            user_roles=user_roles,
            operation=operation,
            **kwargs,
        )

    async def check_department_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        department: str,
        operation: str = "panel_access",
        **kwargs: Any,
    ) -> Result[PermissionResult, PermissionError]:
        """檢查部門權限（主要用於國務院）"""
        # This is a convenience method that delegates to state_council_permission
        return await self.check_state_council_permission(
            guild_id=guild_id,
            user_id=user_id,
            user_roles=user_roles,
            operation=operation,
            department=department,
            **kwargs,
        )
