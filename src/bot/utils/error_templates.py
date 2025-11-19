"""統一錯誤訊息模板。

提供標準化的錯誤訊息格式，確保使用者體驗一致。
"""

from __future__ import annotations

from typing import Any

from src.infra.result import Error


class ErrorMessageTemplates:
    """統一錯誤訊息模板類別。"""

    @staticmethod
    def permission_denied(operation: str, reason: str | None = None) -> str:
        """權限被拒絕的錯誤訊息。"""
        base = "❌ 權限不足"
        if reason:
            return f"{base}：{reason}"
        return f"{base}，無法執行 {operation}。"

    @staticmethod
    def not_configured(feature: str) -> str:
        """功能未設定的錯誤訊息。"""
        return f"⚠️ {feature} 尚未完成設定，請先進行相關配置。"

    @staticmethod
    def not_found(item: str, identifier: str | None = None) -> str:
        """找不到項目的錯誤訊息。"""
        base = f"❌ 找不到 {item}"
        if identifier:
            return f"{base}：{identifier}"
        return f"{base}。"

    @staticmethod
    def validation_failed(field: str, message: str) -> str:
        """驗證失敗的錯誤訊息。"""
        return f"⚠️ {field} 驗證失敗：{message}"

    @staticmethod
    def limit_exceeded(limit_type: str, current: int, maximum: int) -> str:
        """超過限制的錯誤訊息。"""
        return f"⚠️ {limit_type} 已達上限（目前：{current}，上限：{maximum}）"

    @staticmethod
    def insufficient_funds(required: int, available: int) -> str:
        """餘額不足的錯誤訊息。"""
        return f"💰 餘額不足：需要 {required:,}，可用 {available:,}"

    @staticmethod
    def database_error(operation: str) -> str:
        """資料庫錯誤的訊息。"""
        return f"🗄️ 資料庫操作失敗：{operation}，請稍後再試。"

    @staticmethod
    def system_error(message: str | None = None) -> str:
        """系統錯誤的訊息。"""
        base = "🔧 系統發生錯誤"
        if message:
            return f"{base}：{message}"
        return f"{base}，請稍後再試或聯繫管理員。"

    @staticmethod
    def from_error(error: Error | Exception, context: dict[str, Any] | None = None) -> str:
        """從 Error 物件或異常生成統一訊息。"""
        from src.bot.services.council_errors import (
            CouncilError,
            CouncilPermissionDeniedError,
            CouncilValidationError,
            ProposalLimitExceededError,
            ProposalNotFoundError,
            VotingNotAllowedError,
        )
        from src.bot.services.state_council_errors import (
            InsufficientFundsError,
            MonthlyIssuanceLimitExceededError,
            StateCouncilError,
            StateCouncilNotConfiguredError,
            StateCouncilPermissionDeniedError,
            StateCouncilValidationError,
        )

        # 根據錯誤類型選擇適當的模板
        if isinstance(error, CouncilPermissionDeniedError):
            return ErrorMessageTemplates.permission_denied("理事會操作", error.message)
        elif isinstance(error, StateCouncilPermissionDeniedError):
            return ErrorMessageTemplates.permission_denied("國務院操作", error.message)
        elif isinstance(error, CouncilValidationError):
            return ErrorMessageTemplates.validation_failed("資料", error.message)
        elif isinstance(error, StateCouncilValidationError):
            return ErrorMessageTemplates.validation_failed("資料", error.message)
        elif isinstance(error, ProposalNotFoundError):
            return ErrorMessageTemplates.not_found(
                "提案", str(error.context.get("proposal_id", ""))
            )
        elif isinstance(error, ProposalLimitExceededError):
            return ErrorMessageTemplates.limit_exceeded(
                "進行中提案數量", error.context.get("active_count", 0), 5
            )
        elif isinstance(error, VotingNotAllowedError):
            return ErrorMessageTemplates.permission_denied("投票", error.message)
        elif isinstance(error, InsufficientFundsError):
            return ErrorMessageTemplates.insufficient_funds(
                error.context.get("required", 0), error.context.get("available", 0)
            )
        elif isinstance(error, MonthlyIssuanceLimitExceededError):
            return ErrorMessageTemplates.limit_exceeded(
                "月度發行限額", error.context.get("current", 0), error.context.get("limit", 0)
            )
        elif isinstance(error, StateCouncilNotConfiguredError):
            return ErrorMessageTemplates.not_configured("國務院治理")
        elif isinstance(error, (CouncilError, StateCouncilError)):
            # 通用的治理錯誤
            return f"⚠️ 治理操作失敗：{error.message}"
        elif isinstance(error, Error):
            # 通用錯誤
            return f"❌ 操作失敗：{error.message}"
        else:
            # 一般異常或其他類型
            return ErrorMessageTemplates.system_error(str(error))

    @staticmethod
    def format_with_context(message: str, context: dict[str, Any] | None) -> str:
        """為錯誤訊息添加額外上下文。"""
        if not context:
            return message

        # 過濾敏感資訊
        safe_context = {
            k: v
            for k, v in context.items()
            if not any(
                sensitive in k.lower() for sensitive in ["password", "token", "secret", "key"]
            )
        }

        if not safe_context:
            return message

        # 格式化上下文
        context_parts: list[str] = []
        for key, value in safe_context.items():
            if isinstance(value, (int, float)):
                context_parts.append(f"{key}: {value:,}")
            else:
                context_parts.append(f"{key}: {value}")

        if context_parts:
            return f"{message}\n📋 相關資訊：{', '.join(context_parts)}"

        return message


# 快捷函數
def permission_denied(operation: str, reason: str | None = None) -> str:
    """快捷函數：權限被拒絕。"""
    return ErrorMessageTemplates.permission_denied(operation, reason)


def not_configured(feature: str) -> str:
    """快捷函數：功能未設定。"""
    return ErrorMessageTemplates.not_configured(feature)


def validation_failed(field: str, message: str) -> str:
    """快捷函數：驗證失敗。"""
    return ErrorMessageTemplates.validation_failed(field, message)


def system_error(message: str | None = None) -> str:
    """快捷函數：系統錯誤。"""
    return ErrorMessageTemplates.system_error(message)
