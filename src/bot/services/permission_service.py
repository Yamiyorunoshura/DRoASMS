"""
統一權限檢查服務

提供基於Discord身分組的統一權限檢查機制，支援各治理面板的權限控制。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Sequence

import structlog

if TYPE_CHECKING:
    from src.bot.services.council_service import CouncilService
    from src.bot.services.state_council_service import StateCouncilService
    from src.bot.services.supreme_assembly_service import SupremeAssemblyService

LOGGER = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PermissionResult:
    """權限檢查結果"""

    allowed: bool
    reason: str | None = None
    permission_level: str | None = None


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
    ) -> PermissionResult:
        """檢查權限"""
        pass


class CouncilPermissionChecker(PermissionChecker):
    """常任理事會權限檢查器"""

    def __init__(self, council_service: "CouncilService") -> None:
        self._council_service = council_service

    async def check_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> PermissionResult:
        """檢查常任理事會權限"""
        try:
            cfg = await self._council_service.get_config(guild_id=guild_id)
            role_ids = await self._council_service.get_council_role_ids(guild_id=guild_id)
            has_multi_role = bool(set(role_ids) & set(user_roles))
            has_single_role = bool(cfg.council_role_id and cfg.council_role_id in user_roles)
            if not (has_multi_role or has_single_role):
                return PermissionResult(allowed=False, reason="不具備常任理事身分組")

            # 根據操作類型檢查具體權限
            match operation:
                case "panel_access":
                    return PermissionResult(allowed=True, permission_level="council_member")
                case "create_proposal":
                    return PermissionResult(allowed=True, permission_level="council_member")
                case "vote":
                    return PermissionResult(allowed=True, permission_level="council_member")
                case "cancel_proposal":
                    # 提案撤案需要檢查是否為提案人
                    proposer_id = kwargs.get("proposer_id")
                    if proposer_id and user_id == proposer_id:
                        return PermissionResult(allowed=True, permission_level="proposal_owner")
                    return PermissionResult(allowed=False, reason="僅提案人可撤案")
                case _:
                    return PermissionResult(allowed=False, reason=f"未知的操作類型: {operation}")

        except Exception as exc:
            LOGGER.warning(
                "council.permission_check.error",
                guild_id=guild_id,
                user_id=user_id,
                operation=operation,
                error=str(exc),
            )
            return PermissionResult(allowed=False, reason="權限檢查失敗")


class StateCouncilPermissionChecker(PermissionChecker):
    """國務院權限檢查器"""

    def __init__(self, state_council_service: "StateCouncilService") -> None:
        self._state_council_service = state_council_service

    async def check_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> PermissionResult:
        """檢查國務院權限"""
        try:
            # 檢查領導權限
            is_leader = await self._state_council_service.check_leader_permission(
                guild_id=guild_id, user_id=user_id, user_roles=user_roles
            )

            if is_leader:
                return PermissionResult(allowed=True, permission_level="leader")

            # 檢查部門權限
            department = kwargs.get("department")
            if department:
                has_dept_permission = await self._state_council_service.check_department_permission(
                    guild_id=guild_id, user_id=user_id, department=department, user_roles=user_roles
                )

                if has_dept_permission:
                    return PermissionResult(
                        allowed=True,
                        permission_level="department_head",
                        reason=f"具備{department}權限",
                    )

            return PermissionResult(allowed=False, reason="不具備國務院領導或部門權限")

        except Exception as exc:
            LOGGER.warning(
                "state_council.permission_check.error",
                guild_id=guild_id,
                user_id=user_id,
                operation=operation,
                error=str(exc),
            )
            return PermissionResult(allowed=False, reason="權限檢查失敗")


class SupremeAssemblyPermissionChecker(PermissionChecker):
    """最高議會權限檢查器"""

    def __init__(self, supreme_assembly_service: "SupremeAssemblyService") -> None:
        self._supreme_assembly_service = supreme_assembly_service

    async def check_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> PermissionResult:
        """檢查最高議會權限"""
        try:
            cfg = await self._supreme_assembly_service.get_config(guild_id=guild_id)

            # 檢查議長權限
            is_speaker = cfg.speaker_role_id in user_roles

            # 檢查議員權限
            is_member = cfg.member_role_id in user_roles

            match operation:
                case "panel_access":
                    if is_speaker or is_member:
                        level = "speaker" if is_speaker else "member"
                        return PermissionResult(allowed=True, permission_level=level)
                case "create_proposal":
                    if is_speaker or is_member:
                        level = "speaker" if is_speaker else "member"
                        return PermissionResult(allowed=True, permission_level=level)
                case "vote":
                    if is_member:
                        return PermissionResult(allowed=True, permission_level="member")
                case "summon":
                    if is_speaker:
                        return PermissionResult(allowed=True, permission_level="speaker")
                case _:
                    pass

            return PermissionResult(allowed=False, reason="不具備議長或議員身分組")

        except Exception as exc:
            LOGGER.warning(
                "supreme_assembly.permission_check.error",
                guild_id=guild_id,
                user_id=user_id,
                operation=operation,
                error=str(exc),
            )
            return PermissionResult(allowed=False, reason="權限檢查失敗")


class HomelandSecurityPermissionChecker(PermissionChecker):
    """國土安全部權限檢查器"""

    def __init__(self, state_council_service: "StateCouncilService") -> None:
        self._state_council_service = state_council_service

    async def check_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> PermissionResult:
        """檢查國土安全部權限"""
        try:
            # 國土安全部權限通過國務院部門權限檢查
            has_security_permission = await self._state_council_service.check_department_permission(
                guild_id=guild_id, user_id=user_id, department="國土安全部", user_roles=user_roles
            )

            # 檢查是否為國務院領袖（全域權限）
            is_leader = await self._state_council_service.check_leader_permission(
                guild_id=guild_id, user_id=user_id, user_roles=user_roles
            )

            if not (has_security_permission or is_leader):
                return PermissionResult(allowed=False, reason="不具備國土安全部權限")

            # 根據操作類型檢查具體權限
            match operation:
                case "panel_access":
                    level = "leader" if is_leader else "department_head"
                    return PermissionResult(
                        allowed=True,
                        permission_level=level,
                        reason=(
                            "具備國土安全部權限"
                            if has_security_permission
                            else "具備國務院領導權限"
                        ),
                    )
                case "arrest":
                    level = "leader" if is_leader else "department_head"
                    return PermissionResult(
                        allowed=True,
                        permission_level=level,
                        reason=(
                            "具備國土安全部權限"
                            if has_security_permission
                            else "具備國務院領導權限"
                        ),
                    )
                case "release":
                    level = "leader" if is_leader else "department_head"
                    return PermissionResult(
                        allowed=True,
                        permission_level=level,
                        reason=(
                            "具備國土安全部權限"
                            if has_security_permission
                            else "具備國務院領導權限"
                        ),
                    )
                case "suspect_management":
                    level = "leader" if is_leader else "department_head"
                    return PermissionResult(
                        allowed=True,
                        permission_level=level,
                        reason=(
                            "具備國土安全部權限"
                            if has_security_permission
                            else "具備國務院領導權限"
                        ),
                    )
                case _:
                    return PermissionResult(allowed=False, reason=f"未知的操作類型: {operation}")

        except Exception as exc:
            LOGGER.warning(
                "homeland_security.permission_check.error",
                guild_id=guild_id,
                user_id=user_id,
                operation=operation,
                error=str(exc),
            )
            return PermissionResult(allowed=False, reason="權限檢查失敗")


class SupremePeoplesAssemblyPermissionChecker(PermissionChecker):
    """最高人民議會權限檢查器"""

    def __init__(self, supreme_assembly_service: "SupremeAssemblyService") -> None:
        self._supreme_assembly_service = supreme_assembly_service

    async def check_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> PermissionResult:
        """檢查最高人民議會權限"""
        try:
            cfg = await self._supreme_assembly_service.get_config(guild_id=guild_id)

            # 檢查議長權限
            is_speaker = cfg.speaker_role_id in user_roles

            # 檢查人民代表（議員）權限
            is_representative = cfg.member_role_id in user_roles

            match operation:
                case "panel_access":
                    # 人民代表和議長都可以開啟面板
                    if is_speaker or is_representative:
                        level = "speaker" if is_speaker else "representative"
                        return PermissionResult(
                            allowed=True,
                            permission_level=level,
                            reason=f"具備{'議長' if is_speaker else '人民代表'}身分組",
                        )
                case "create_proposal":
                    # 人民代表可以發起提案，議長同樣具備權限
                    if is_speaker or is_representative:
                        level = "speaker" if is_speaker else "representative"
                        return PermissionResult(
                            allowed=True,
                            permission_level=level,
                            reason=f"具備{'議長' if is_speaker else '人民代表'}身分組",
                        )
                case "vote":
                    # 人民代表可以投票
                    if is_representative:
                        return PermissionResult(
                            allowed=True,
                            permission_level="representative",
                            reason="具備人民代表身分組",
                        )
                case "summon":
                    # 只有議長可以傳召
                    if is_speaker:
                        return PermissionResult(
                            allowed=True, permission_level="speaker", reason="具備議長身分組"
                        )
                case "transfer":
                    # 人民代表和議長都可以進行轉帳
                    if is_speaker or is_representative:
                        level = "speaker" if is_speaker else "representative"
                        return PermissionResult(
                            allowed=True,
                            permission_level=level,
                            reason=f"具備{'議長' if is_speaker else '人民代表'}身分組",
                        )
                case _:
                    return PermissionResult(allowed=False, reason=f"未知的操作類型: {operation}")

            return PermissionResult(allowed=False, reason="不具備議長或人民代表身分組")

        except Exception as exc:
            LOGGER.warning(
                "supreme_peoples_assembly.permission_check.error",
                guild_id=guild_id,
                user_id=user_id,
                operation=operation,
                error=str(exc),
            )
            return PermissionResult(allowed=False, reason="權限檢查失敗")


class PermissionService:
    """統一權限檢查服務"""

    def __init__(
        self,
        *,
        council_service: "CouncilService",
        state_council_service: "StateCouncilService",
        supreme_assembly_service: "SupremeAssemblyService",
    ) -> None:
        self._council_checker = CouncilPermissionChecker(council_service)
        self._state_council_checker = StateCouncilPermissionChecker(state_council_service)
        self._supreme_assembly_checker = SupremeAssemblyPermissionChecker(supreme_assembly_service)
        self._homeland_security_checker = HomelandSecurityPermissionChecker(state_council_service)
        self._supreme_peoples_assembly_checker = SupremePeoplesAssemblyPermissionChecker(
            supreme_assembly_service
        )

    async def check_council_permission(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: Sequence[int],
        operation: str,
        **kwargs: Any,
    ) -> PermissionResult:
        """檢查常任理事會權限"""
        return await self._council_checker.check_permission(
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
    ) -> PermissionResult:
        """檢查國務院部門權限"""
        return await self._state_council_checker.check_permission(
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
    ) -> PermissionResult:
        """檢查國土安全部權限"""
        return await self._homeland_security_checker.check_permission(
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
    ) -> PermissionResult:
        """檢查最高議會權限"""
        return await self._supreme_assembly_checker.check_permission(
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
    ) -> PermissionResult:
        """檢查最高人民議會權限"""
        return await self._supreme_peoples_assembly_checker.check_permission(
            guild_id=guild_id, user_id=user_id, user_roles=user_roles, operation=operation, **kwargs
        )


# 工廠函數
def create_permission_service(
    *,
    council_service: "CouncilService",
    state_council_service: "StateCouncilService",
    supreme_assembly_service: "SupremeAssemblyService",
) -> PermissionService:
    """創建權限服務實例"""
    return PermissionService(
        council_service=council_service,
        state_council_service=state_council_service,
        supreme_assembly_service=supreme_assembly_service,
    )


__all__ = [
    "PermissionService",
    "PermissionResult",
    "PermissionChecker",
    "create_permission_service",
]
