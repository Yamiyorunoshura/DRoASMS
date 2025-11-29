"""Result-first permission checking service for governance commands."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Sequence, TypeVar, cast

import structlog

from src.infra.result import Err, Error, Ok, Result
from src.infra.result_compat import mark_migrated

if TYPE_CHECKING:
    from src.bot.services.council_service import CouncilService, CouncilServiceResult
    from src.bot.services.state_council_service import StateCouncilService
    from src.bot.services.supreme_assembly_service import SupremeAssemblyService
    from src.db.gateway.council_governance import CouncilConfig
    from src.db.gateway.supreme_assembly_governance import SupremeAssemblyConfig

LOGGER = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PermissionResult:
    """結果物件：描述權限判斷結果與理由。"""

    allowed: bool
    reason: str | None = None
    permission_level: str | None = None


class PermissionError(Error):
    """統一的權限檢查錯誤型別。"""


TResult = TypeVar("TResult")


async def _await_result(
    awaitable: Awaitable[object],
    *,
    failure_message: str,
    log_event: str,
    log_context: dict[str, Any],
) -> Result[TResult, Error]:
    try:
        response = await awaitable
    except Error as error:
        return Err(error)
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.warning(log_event, **log_context, error=str(exc))
        return Err(PermissionError(failure_message, cause=exc))

    if isinstance(response, Err):
        return cast(Result[TResult, Error], response)
    if isinstance(response, Ok):
        return cast(Result[TResult, Error], response)
    return cast(Result[TResult, Error], Ok(cast(TResult, response)))


class PermissionChecker(ABC):
    """權限檢查器抽象基類，統一以 Result 回傳。"""

    @abstractmethod
    async def check_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> Result[PermissionResult, Error]:
        """執行權限檢查並回傳 Result。"""


class CouncilPermissionChecker(PermissionChecker):
    """Result 版常任理事會權限檢查器。"""

    def __init__(
        self,
        council_service: "CouncilServiceResult | CouncilService",
    ) -> None:
        self._council_service = council_service

    async def check_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> Result[PermissionResult, Error]:
        config_result: Result["CouncilConfig", Error] = await _await_result(
            self._council_service.get_config(guild_id=guild_id),
            failure_message="常任理事會設定錯誤",
            log_event="council.permission.config.error",
            log_context={
                "guild_id": guild_id,
                "user_id": user_id,
                "operation": operation,
            },
        )
        if isinstance(config_result, Err):
            return Err(config_result.error)
        config = config_result.value

        role_ids_result: Result[Sequence[int] | None, Error] = await _await_result(
            self._council_service.get_council_role_ids(guild_id=guild_id),
            failure_message="常任理事會權限檢查失敗",
            log_event="council.permission.role_ids.error",
            log_context={
                "guild_id": guild_id,
                "user_id": user_id,
                "operation": operation,
            },
        )
        if isinstance(role_ids_result, Err):
            return Err(role_ids_result.error)

        role_ids = list(role_ids_result.value or [])
        has_multi_role = bool(set(role_ids) & set(user_roles))
        has_single_role = bool(config.council_role_id and config.council_role_id in user_roles)

        if not (has_multi_role or has_single_role):
            return Ok(PermissionResult(allowed=False, reason="不具備常任理事身分組"))

        match operation:
            case "panel_access" | "create_proposal" | "vote":
                return Ok(PermissionResult(allowed=True, permission_level="council_member"))
            case "cancel_proposal":
                proposer_id = kwargs.get("proposer_id")
                if proposer_id and proposer_id == user_id:
                    return Ok(PermissionResult(allowed=True, permission_level="proposal_owner"))
                return Ok(PermissionResult(allowed=False, reason="僅提案人可撤案"))
            case _:
                return Ok(PermissionResult(allowed=False, reason=f"未知的操作類型: {operation}"))


class StateCouncilPermissionChecker(PermissionChecker):
    """國務院權限檢查器，整合領導與部門權限。"""

    def __init__(
        self,
        state_council_service: "StateCouncilService",
    ) -> None:
        self._state_council = state_council_service

    async def _has_leader_permission(
        self, *, guild_id: int, user_id: int, user_roles: Sequence[int]
    ) -> Result[bool, Error]:
        leader_result: Result[bool, Error] = await _await_result(
            self._state_council.check_leader_permission(
                guild_id=guild_id,
                user_id=user_id,
                user_roles=user_roles,
            ),
            failure_message="國務院領導權限檢查失敗",
            log_event="state_council.permission.leader.error",
            log_context={
                "guild_id": guild_id,
                "user_id": user_id,
            },
        )
        if isinstance(leader_result, Err):
            return Err(leader_result.error)
        return Ok(bool(leader_result.value))

    async def _has_department_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        department: str | None,
        user_roles: Sequence[int],
    ) -> Result[bool, Error]:
        if department is None:
            return Ok(False)
        awaitable = self._state_council.check_department_permission(
            guild_id=guild_id,
            user_id=user_id,
            department=department,
            user_roles=user_roles,
        )
        dept_result: Result[bool, Error] = await _await_result(
            awaitable,
            failure_message="國務院部門權限檢查失敗",
            log_event="state_council.permission.department.error",
            log_context={
                "guild_id": guild_id,
                "user_id": user_id,
                "department": department,
            },
        )
        if isinstance(dept_result, Err):
            return Err(dept_result.error)
        return Ok(bool(dept_result.value))

    async def check_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> Result[PermissionResult, Error]:
        department = kwargs.get("department") or kwargs.get("department_id")

        leader_result = await self._has_leader_permission(
            guild_id=guild_id, user_id=user_id, user_roles=user_roles
        )
        if isinstance(leader_result, Err):
            return Err(leader_result.error)

        dept_result = await self._has_department_permission(
            guild_id=guild_id,
            user_id=user_id,
            department=department,
            user_roles=user_roles,
        )
        if isinstance(dept_result, Err):
            return Err(dept_result.error)

        is_leader = leader_result.value
        has_dept_permission = dept_result.value

        if not (is_leader or has_dept_permission):
            return Ok(PermissionResult(allowed=False, reason="不具備國務院領導或部門權限"))

        level = "leader" if is_leader else "department_head"
        return Ok(
            PermissionResult(
                allowed=True,
                permission_level=level,
                reason=(
                    "具備國務院領導權限" if is_leader else f"具備{department or '指定部門'}權限"
                ),
            )
        )


class SupremeAssemblyPermissionChecker(PermissionChecker):
    """最高議會權限檢查器。"""

    def __init__(
        self,
        supreme_assembly_service: "SupremeAssemblyService",
    ) -> None:
        self._supreme_assembly_service = supreme_assembly_service

    async def check_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> Result[PermissionResult, Error]:
        config_result: Result["SupremeAssemblyConfig", Error] = await _await_result(
            self._supreme_assembly_service.get_config(guild_id=guild_id),
            failure_message="最高議會設定錯誤",
            log_event="supreme_assembly.permission_check.error",
            log_context={
                "guild_id": guild_id,
                "user_id": user_id,
                "operation": operation,
            },
        )
        if isinstance(config_result, Err):
            return Err(config_result.error)
        cfg = config_result.value

        is_speaker = cfg.speaker_role_id in user_roles
        is_member = cfg.member_role_id in user_roles

        match operation:
            case "panel_access" | "create_proposal":
                if is_speaker or is_member:
                    level = "speaker" if is_speaker else "member"
                    return Ok(
                        PermissionResult(
                            allowed=True,
                            permission_level=level,
                            reason=f"具備{'議長' if is_speaker else '議員'}身分組",
                        )
                    )
            case "vote":
                if is_member:
                    return Ok(
                        PermissionResult(
                            allowed=True,
                            permission_level="member",
                            reason="具備議員身分組",
                        )
                    )
            case "summon":
                if is_speaker:
                    return Ok(PermissionResult(allowed=True, permission_level="speaker"))
            case _:
                pass
        return Ok(PermissionResult(allowed=False, reason="不具備議長或議員身分組"))


class HomelandSecurityPermissionChecker(PermissionChecker):
    """國土安全部權限檢查器。"""

    def __init__(
        self,
        state_council_service: "StateCouncilService",
    ) -> None:
        self._state_council = state_council_service
        self._delegate = StateCouncilPermissionChecker(state_council_service)

    async def check_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> Result[PermissionResult, Error]:
        # 僅允許已知的國土安全相關操作
        allowed_operations = {"panel_access", "arrest", "release", "suspect_management"}
        if operation not in allowed_operations:
            return Ok(PermissionResult(allowed=False, reason=f"未知的操作類型: {operation}"))

        result = await self._delegate.check_permission(
            guild_id=guild_id,
            user_id=user_id,
            user_roles=user_roles,
            operation=operation,
            department="國土安全部",
        )
        if isinstance(result, Err):
            return result

        permission = result.value
        if not permission.allowed:
            return Ok(PermissionResult(allowed=False, reason="不具備國土安全部權限"))

        # 對於國土安全部，我們將理由與層級調整為更具體的描述
        if permission.permission_level == "leader":
            return Ok(
                PermissionResult(
                    allowed=True,
                    permission_level="leader",
                    reason="具備國務院領導權限",
                )
            )

        return Ok(
            PermissionResult(
                allowed=True,
                permission_level="department_head",
                reason="具備國土安全部權限",
            )
        )


class SupremePeoplesAssemblyPermissionChecker(PermissionChecker):
    """最高人民議會權限檢查器。"""

    def __init__(
        self,
        supreme_assembly_service: "SupremeAssemblyService",
    ) -> None:
        self._supreme_assembly_service = supreme_assembly_service

    async def check_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> Result[PermissionResult, Error]:
        config_result: Result["SupremeAssemblyConfig", Error] = await _await_result(
            self._supreme_assembly_service.get_config(guild_id=guild_id),
            failure_message="最高人民議會設定錯誤",
            log_event="supreme_peoples_assembly.permission_check.error",
            log_context={
                "guild_id": guild_id,
                "user_id": user_id,
                "operation": operation,
            },
        )
        if isinstance(config_result, Err):
            return Err(config_result.error)
        cfg = config_result.value

        is_speaker = cfg.speaker_role_id in user_roles
        is_representative = cfg.member_role_id in user_roles

        match operation:
            case "panel_access" | "create_proposal" | "transfer":
                if is_speaker or is_representative:
                    level = "speaker" if is_speaker else "representative"
                    return Ok(
                        PermissionResult(
                            allowed=True,
                            permission_level=level,
                            reason=f"具備{'議長' if is_speaker else '人民代表'}身分組",
                        )
                    )
            case "vote":
                if is_representative:
                    return Ok(
                        PermissionResult(
                            allowed=True,
                            permission_level="representative",
                            reason="具備人民代表身分組",
                        )
                    )
            case "summon":
                if is_speaker:
                    return Ok(
                        PermissionResult(
                            allowed=True,
                            permission_level="speaker",
                            reason="具備議長身分組",
                        )
                    )
            case _:
                pass
        # 未知操作一律視為不允許，並提供明確提示；
        # 對於已知操作但缺乏身分組，回傳一般的「不具備身分組」訊息。
        known_operations = {"panel_access", "create_proposal", "vote", "summon", "transfer"}
        if operation not in known_operations:
            return Ok(PermissionResult(allowed=False, reason=f"未知的操作類型: {operation}"))
        return Ok(PermissionResult(allowed=False, reason="不具備議長或人民代表身分組"))


class PermissionService:
    """統一 Result 版權限檢查服務。"""

    def __init__(
        self,
        *,
        council_service: "CouncilServiceResult | CouncilService",
        state_council_service: "StateCouncilService",
        supreme_assembly_service: "SupremeAssemblyService",
    ) -> None:
        council_checker = CouncilPermissionChecker(council_service)
        state_council_checker = StateCouncilPermissionChecker(state_council_service)
        supreme_assembly_checker = SupremeAssemblyPermissionChecker(supreme_assembly_service)
        homeland_checker = HomelandSecurityPermissionChecker(state_council_service)
        supreme_peoples_checker = SupremePeoplesAssemblyPermissionChecker(supreme_assembly_service)

        # 兼容舊有直接存取欄位的呼叫者
        self._council_checker = council_checker
        self._state_council_checker = state_council_checker
        self._supreme_assembly_checker = supreme_assembly_checker
        self._homeland_security_checker = homeland_checker
        self._supreme_peoples_assembly_checker = supreme_peoples_checker

        self._checkers: dict[str, PermissionChecker] = {
            "council": council_checker,
            "state_council": state_council_checker,
            "supreme_assembly": supreme_assembly_checker,
            "homeland_security": homeland_checker,
            "supreme_peoples_assembly": supreme_peoples_checker,
        }

    def _get_checker(self, key: str) -> PermissionChecker | None:
        return self._checkers.get(key)

    async def check_council_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> Result[PermissionResult, Error]:
        checker = self._get_checker("council")
        if checker is None:
            return Err(PermissionError("常任理事會服務未初始化"))
        return await checker.check_permission(
            guild_id=guild_id, user_id=user_id, user_roles=user_roles, operation=operation, **kwargs
        )

    async def check_state_council_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> Result[PermissionResult, Error]:
        checker = self._get_checker("state_council")
        if checker is None:
            return Err(PermissionError("國務院服務未初始化"))
        return await checker.check_permission(
            guild_id=guild_id, user_id=user_id, user_roles=user_roles, operation=operation, **kwargs
        )

    async def check_department_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        department: str,
        operation: str,
        **kwargs: Any,
    ) -> Result[PermissionResult, Error]:
        return await self.check_state_council_permission(
            guild_id=guild_id,
            user_id=user_id,
            user_roles=user_roles,
            operation=operation,
            department=department,
            **kwargs,
        )

    async def check_homeland_security_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> Result[PermissionResult, Error]:
        checker = self._get_checker("homeland_security")
        if checker is None:
            return Err(PermissionError("國土安全部服務未初始化"))
        return await checker.check_permission(
            guild_id=guild_id, user_id=user_id, user_roles=user_roles, operation=operation, **kwargs
        )

    async def check_supreme_assembly_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> Result[PermissionResult, Error]:
        checker = self._get_checker("supreme_assembly")
        if checker is None:
            return Err(PermissionError("最高議會服務未初始化"))
        return await checker.check_permission(
            guild_id=guild_id, user_id=user_id, user_roles=user_roles, operation=operation, **kwargs
        )

    async def check_supreme_peoples_assembly_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> Result[PermissionResult, Error]:
        checker = self._get_checker("supreme_peoples_assembly")
        if checker is None:
            return Err(PermissionError("最高人民議會服務未初始化"))
        return await checker.check_permission(
            guild_id=guild_id, user_id=user_id, user_roles=user_roles, operation=operation, **kwargs
        )


__all__ = [
    "PermissionService",
    "PermissionResult",
    "PermissionError",
    "PermissionChecker",
]


mark_migrated("src.bot.services.permission_service.PermissionService")
