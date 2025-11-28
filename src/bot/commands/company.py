"""公司管理指令模組。

提供 /company panel 指令，允許持有商業許可的用戶管理公司。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence, cast

if TYPE_CHECKING:
    from typing import Self
from uuid import UUID

import discord
import structlog
from discord import app_commands

from src.bot.commands.help_data import HelpData
from src.bot.interaction_compat import (
    edit_message_compat,
    send_message_compat,
    send_modal_compat,
)
from src.bot.services.company_service import (
    CompanyLicenseInvalidError,
    CompanyService,
    InvalidCompanyNameError,
    LicenseAlreadyUsedError,
    NoAvailableLicenseError,
)
from src.bot.services.currency_config_service import (
    CurrencyConfigResult,
    CurrencyConfigService,
)
from src.bot.ui.base import PersistentPanelView
from src.cython_ext.state_council_models import (
    Company,
)
from src.infra.di.container import DependencyContainer
from src.infra.result import Err, Ok

LOGGER = structlog.get_logger(__name__)


def _format_currency_display(currency_config: CurrencyConfigResult, amount: int) -> str:
    """Format currency amount with configured name and icon."""
    if currency_config.currency_icon and currency_config.currency_name:
        currency_display = f"{currency_config.currency_icon} {currency_config.currency_name}"
    elif currency_config.currency_icon:
        currency_display = f"{currency_config.currency_icon}"
    else:
        currency_display = currency_config.currency_name
    return f"{amount:,} {currency_display}"


def get_help_data() -> dict[str, HelpData]:
    """Return help information for company commands."""
    return {
        "company": {
            "name": "company",
            "description": "公司管理指令群組",
            "category": "economy",
            "parameters": [],
            "permissions": [],
            "examples": [],
            "tags": ["公司", "經濟"],
        },
        "company panel": {
            "name": "company panel",
            "description": "開啟公司面板。查看現有公司或成立新公司。",
            "category": "economy",
            "parameters": [],
            "permissions": [],
            "examples": ["/company panel"],
            "tags": ["面板", "公司"],
        },
    }


def register(
    tree: app_commands.CommandTree, *, container: DependencyContainer | None = None
) -> None:
    """Register the /company slash command group with the provided command tree."""
    if container is None:
        from src.db import pool as db_pool

        pool = db_pool.get_pool()
        company_service = CompanyService(pool)
        currency_service = CurrencyConfigService(pool)
    else:
        company_service = container.resolve(CompanyService)
        currency_service = container.resolve(CurrencyConfigService)

    tree.add_command(build_company_group(company_service, currency_service))
    LOGGER.debug("bot.command.company.registered")


def build_company_group(
    company_service: CompanyService,
    currency_service: CurrencyConfigService,
) -> app_commands.Group:
    """建立 /company 指令群組。"""
    company = app_commands.Group(name="company", description="公司管理指令")

    @company.command(name="panel", description="開啟公司面板")
    async def panel(  # pyright: ignore[reportUnusedFunction]
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild_id is None or interaction.guild is None:
            await send_message_compat(
                interaction, content="本指令需在伺服器中執行。", ephemeral=True
            )
            return

        # Defer to avoid timeout
        try:
            response = getattr(interaction, "response", None)
            is_done_attr = getattr(response, "is_done", None)
            already_done = bool(is_done_attr()) if callable(is_done_attr) else bool(is_done_attr)
            if response is not None and not already_done:
                await response.defer(ephemeral=True, thinking=True)
        except Exception as exc:
            LOGGER.warning(
                "company.panel.defer_failed",
                guild_id=interaction.guild_id,
                user_id=getattr(interaction, "user", None) and interaction.user.id,
                error=str(exc),
            )

        # Get currency config
        currency_config = await currency_service.get_currency_config(guild_id=interaction.guild_id)

        # Create panel view
        view = CompanyPanelView(
            company_service=company_service,
            currency_service=currency_service,
            guild_id=interaction.guild_id,
            author_id=interaction.user.id,
            currency_config=currency_config,
        )

        embed = await view.build_home_embed()
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)

        LOGGER.info(
            "company.panel.open",
            guild_id=interaction.guild_id,
            user_id=interaction.user.id,
        )

    # Add compatibility shim for tests
    try:
        cast(Any, company).children = company.commands
    except Exception:
        pass
    try:
        from discord import AppCommandOptionType

        cast(Any, company).type = AppCommandOptionType.subcommand_group
    except Exception:
        pass

    return company


class CompanyPanelView(PersistentPanelView):
    """公司面板容器。"""

    panel_type = "company"

    def __init__(
        self,
        *,
        company_service: CompanyService,
        currency_service: CurrencyConfigService,
        guild_id: int,
        author_id: int,
        currency_config: CurrencyConfigResult,
    ) -> None:
        super().__init__(author_id=author_id, timeout=600.0)
        self.company_service = company_service
        self.currency_service = currency_service
        self.guild_id = guild_id
        self.currency_config = currency_config

        # Current state
        self.current_page = "home"  # home, detail, transfer
        self.current_company: Company | None = None
        self.companies: Sequence[Company] = []

        # Pending state (public for modal access)
        self.pending_license_id: UUID | None = None

        # Note: View items will be updated after build_home_embed loads companies

    async def build_home_embed(self) -> discord.Embed:
        """Build the home page embed showing company list."""
        # Fetch companies (author_id is guaranteed non-None in CompanyPanelView)
        assert self.author_id is not None
        result = await self.company_service.list_user_companies(
            guild_id=self.guild_id, owner_id=self.author_id
        )
        if isinstance(result, Err):
            self.companies = []
        else:
            self.companies = result.value

        embed = discord.Embed(
            title="🏢 公司面板",
            color=0x3498DB,
        )

        if not self.companies:
            embed.description = "您目前沒有任何公司。\n\n點擊下方按鈕成立公司。"
        else:
            embed.description = "以下是您擁有的公司列表。"

            for company in self.companies:
                # Get balance
                balance_result = await self.company_service.get_company_balance(
                    guild_id=self.guild_id, account_id=company.account_id
                )
                balance = balance_result.value if isinstance(balance_result, Ok) else 0

                license_info = company.license_type or "未知"
                status = "✅ 有效" if company.license_status == "active" else "❌ 失效"

                embed.add_field(
                    name=f"📋 {company.name}",
                    value=(
                        f"許可類型：{license_info}\n"
                        f"狀態：{status}\n"
                        f"餘額：{_format_currency_display(self.currency_config, balance)}"
                    ),
                    inline=False,
                )

        embed.set_footer(text="使用下方按鈕管理公司")

        # Update view items after loading companies
        self.update_view_items()

        return embed

    async def build_detail_embed(self) -> discord.Embed:
        """Build the company detail page embed."""
        if self.current_company is None:
            return await self.build_home_embed()

        company = self.current_company

        # Get balance
        balance_result = await self.company_service.get_company_balance(
            guild_id=self.guild_id, account_id=company.account_id
        )
        balance = balance_result.value if isinstance(balance_result, Ok) else 0

        embed = discord.Embed(
            title=f"🏢 {company.name}",
            color=0x2ECC71,
        )

        license_info = company.license_type or "未知"
        status = "✅ 有效" if company.license_status == "active" else "❌ 失效"
        created_at = company.created_at.strftime("%Y-%m-%d %H:%M")

        embed.add_field(
            name="📋 公司資訊",
            value=(
                f"**許可類型：** {license_info}\n"
                f"**狀態：** {status}\n"
                f"**創建時間：** {created_at}"
            ),
            inline=False,
        )

        embed.add_field(
            name="💰 帳戶餘額",
            value=f"**{_format_currency_display(self.currency_config, balance)}**",
            inline=False,
        )

        embed.set_footer(text="使用下方按鈕進行操作")
        return embed

    def update_view_items(self) -> None:
        """Update view components based on current page."""
        self.clear_items()

        if self.current_page == "home":
            self._add_home_items()
        elif self.current_page == "detail":
            self._add_detail_items()
        elif self.current_page == "transfer":
            self._add_transfer_items()

    def _add_home_items(self) -> None:
        """Add home page items."""
        # Create company button
        create_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="成立公司",
            style=discord.ButtonStyle.success,
            custom_id="create_company",
            row=0,
        )
        create_btn.callback = self._on_create_company
        self.add_item(create_btn)

        # Company selection dropdown (if has companies)
        if self.companies:
            options = [
                discord.SelectOption(
                    label=c.name[:50],
                    value=str(c.id),
                    description=f"許可：{c.license_type or '未知'}"[:50],
                )
                for c in self.companies[:25]  # Discord limit
            ]

            class _CompanySelect(discord.ui.Select[Any]):
                pass

            select = _CompanySelect(
                placeholder="選擇要管理的公司",
                options=options,
                row=1,
            )

            async def _on_company_select(interaction: discord.Interaction) -> None:
                if interaction.user.id != self.author_id:
                    await send_message_compat(
                        interaction, content="僅限面板開啟者操作。", ephemeral=True
                    )
                    return

                company_id = int(select.values[0])
                # Find the selected company
                for c in self.companies:
                    if c.id == company_id:
                        self.current_company = c
                        break

                self.current_page = "detail"
                self.update_view_items()
                embed = await self.build_detail_embed()
                await edit_message_compat(interaction, embed=embed, view=self)

            select.callback = _on_company_select
            self.add_item(select)

    def _add_detail_items(self) -> None:
        """Add detail page items."""
        # Transfer button
        transfer_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="轉帳",
            style=discord.ButtonStyle.primary,
            custom_id="transfer",
            row=0,
        )
        transfer_btn.callback = self._on_transfer
        self.add_item(transfer_btn)

        # Back button
        back_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="返回列表",
            style=discord.ButtonStyle.secondary,
            custom_id="back",
            row=0,
        )
        back_btn.callback = self._on_back
        self.add_item(back_btn)

    def _add_transfer_items(self) -> None:
        """Add transfer page items."""
        # Transfer to user button
        transfer_user_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="轉帳給使用者",
            style=discord.ButtonStyle.primary,
            custom_id="transfer_user",
            row=0,
        )
        transfer_user_btn.callback = self._on_transfer_user
        self.add_item(transfer_user_btn)

        # Transfer to government button
        transfer_gov_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="轉帳給政府部門",
            style=discord.ButtonStyle.secondary,
            custom_id="transfer_gov",
            row=0,
        )
        transfer_gov_btn.callback = self._on_transfer_gov
        self.add_item(transfer_gov_btn)

        # Back button
        back_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="返回詳情",
            style=discord.ButtonStyle.secondary,
            custom_id="back_detail",
            row=1,
        )
        back_btn.callback = self._on_back_detail
        self.add_item(back_btn)

    async def _on_create_company(self, interaction: discord.Interaction) -> None:
        """Handle create company button click."""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        # Get available licenses (author_id is guaranteed non-None in CompanyPanelView)
        assert self.author_id is not None
        result = await self.company_service.get_available_licenses(
            guild_id=self.guild_id, user_id=self.author_id
        )

        if isinstance(result, Err):
            await send_message_compat(
                interaction, content="無法取得許可證列表，請稍後再試。", ephemeral=True
            )
            return

        licenses = result.value
        if not licenses:
            await send_message_compat(
                interaction,
                content="您沒有可用的商業許可，請先申請商業許可。",
                ephemeral=True,
            )
            return

        # Show license selection
        options = [
            discord.SelectOption(
                label=f"{lic.license_type}"[:50],
                value=str(lic.license_id),
                description=f"到期：{lic.expires_at.strftime('%Y-%m-%d')}"[:50],
            )
            for lic in licenses[:25]
        ]

        class _LicenseSelect(discord.ui.Select[Any]):
            pass

        select = _LicenseSelect(
            placeholder="選擇要使用的許可證",
            options=options,
        )

        async def _on_license_select(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return

            self.pending_license_id = UUID(select.values[0])

            # Show company name modal
            modal = CompanyNameModal(self)
            await send_modal_compat(interaction, modal)

        select.callback = _on_license_select

        # Create temporary view for license selection
        temp_view = discord.ui.View(timeout=60)
        temp_view.add_item(select)

        await send_message_compat(
            interaction,
            content="請選擇要用於成立公司的許可證：",
            view=temp_view,
            ephemeral=True,
        )

    async def _on_transfer(self, interaction: discord.Interaction) -> None:
        """Handle transfer button click."""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        if self.current_company is None:
            await send_message_compat(interaction, content="請先選擇一家公司。", ephemeral=True)
            return

        # Validate company can operate (author_id is guaranteed non-None in CompanyPanelView)
        assert self.author_id is not None
        result = await self.company_service.validate_company_operation(
            company_id=self.current_company.id, user_id=self.author_id
        )
        if isinstance(result, Err):
            error = result.error
            if isinstance(error, CompanyLicenseInvalidError):
                await send_message_compat(
                    interaction, content="此公司的商業許可已失效。", ephemeral=True
                )
            else:
                await send_message_compat(interaction, content=str(error), ephemeral=True)
            return

        self.current_page = "transfer"
        self.update_view_items()

        embed = discord.Embed(
            title=f"💸 轉帳 - {self.current_company.name}",
            description="選擇轉帳對象",
            color=0xE74C3C,
        )
        await edit_message_compat(interaction, embed=embed, view=self)

    async def _on_transfer_user(self, interaction: discord.Interaction) -> None:
        """Handle transfer to user button click."""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        if self.current_company is None:
            await send_message_compat(interaction, content="請先選擇一家公司。", ephemeral=True)
            return

        # Show user select
        class _UserSelect(discord.ui.UserSelect[Any]):
            pass

        select = _UserSelect(placeholder="選擇收款人")

        async def _on_user_select(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return

            target_user = select.values[0]
            modal = CompanyTransferModal(
                self,
                target_id=target_user.id,
                target_name=target_user.display_name,
                target_type="user",
            )
            await send_modal_compat(interaction, modal)

        select.callback = _on_user_select

        temp_view = discord.ui.View(timeout=60)
        temp_view.add_item(select)

        await send_message_compat(
            interaction,
            content="請選擇收款人：",
            view=temp_view,
            ephemeral=True,
        )

    async def _on_transfer_gov(self, interaction: discord.Interaction) -> None:
        """Handle transfer to government button click."""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        if self.current_company is None:
            await send_message_compat(interaction, content="請先選擇一家公司。", ephemeral=True)
            return

        # Show department select
        departments = [
            ("內政部", "interior"),
            ("財政部", "finance"),
            ("國土安全部", "security"),
            ("中央銀行", "central_bank"),
            ("法務部", "justice"),
        ]

        options = [discord.SelectOption(label=name, value=value) for name, value in departments]

        class _DeptSelect(discord.ui.Select[Any]):
            pass

        select = _DeptSelect(
            placeholder="選擇收款部門",
            options=options,
        )

        async def _on_dept_select(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return

            dept_value = select.values[0]
            dept_name = next((n for n, v in departments if v == dept_value), dept_value)

            modal = CompanyTransferModal(
                self,
                target_id=0,  # Will be resolved later
                target_name=dept_name,
                target_type="department",
                department=dept_value,
            )
            await send_modal_compat(interaction, modal)

        select.callback = _on_dept_select

        temp_view = discord.ui.View(timeout=60)
        temp_view.add_item(select)

        await send_message_compat(
            interaction,
            content="請選擇收款部門：",
            view=temp_view,
            ephemeral=True,
        )

    async def _on_back(self, interaction: discord.Interaction) -> None:
        """Handle back button click from detail to home."""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        self.current_page = "home"
        self.current_company = None
        self.update_view_items()
        embed = await self.build_home_embed()
        await edit_message_compat(interaction, embed=embed, view=self)

    async def _on_back_detail(self, interaction: discord.Interaction) -> None:
        """Handle back button click from transfer to detail."""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        self.current_page = "detail"
        self.update_view_items()
        embed = await self.build_detail_embed()
        await edit_message_compat(interaction, embed=embed, view=self)


class CompanyNameModal(discord.ui.Modal):
    """Modal for entering company name."""

    name_input: discord.ui.TextInput["Self"] = discord.ui.TextInput(
        label="公司名稱",
        placeholder="請輸入公司名稱（1-100 字元）",
        min_length=1,
        max_length=100,
        required=True,
    )

    def __init__(self, panel: CompanyPanelView) -> None:
        super().__init__(title="成立公司")
        self.panel = panel

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if self.panel.pending_license_id is None:
            await send_message_compat(interaction, content="請重新選擇許可證。", ephemeral=True)
            return

        name = self.name_input.value.strip()

        # Create company (author_id is guaranteed non-None in CompanyPanelView)
        assert self.panel.author_id is not None
        result = await self.panel.company_service.create_company(
            guild_id=self.panel.guild_id,
            owner_id=self.panel.author_id,
            license_id=self.panel.pending_license_id,
            name=name,
        )

        if isinstance(result, Err):
            error = result.error
            if isinstance(error, NoAvailableLicenseError):
                msg = "您沒有可用的商業許可，請先申請商業許可。"
            elif isinstance(error, LicenseAlreadyUsedError):
                msg = "此許可證已關聯一家公司。"
            elif isinstance(error, InvalidCompanyNameError):
                msg = "公司名稱必須為 1-100 個字元。"
            else:
                msg = f"創建失敗：{error}"

            await send_message_compat(interaction, content=msg, ephemeral=True)
            return

        # Success - refresh the panel
        self.panel.pending_license_id = None
        self.panel.current_page = "home"
        self.panel.update_view_items()

        await send_message_compat(
            interaction,
            content=f"公司成立成功！「{name}」已創建。",
            ephemeral=True,
        )

        LOGGER.info(
            "company.created",
            guild_id=self.panel.guild_id,
            owner_id=self.panel.author_id,
            company_id=result.value.id,
            company_name=name,
        )


class CompanyTransferModal(discord.ui.Modal):
    """Modal for company transfer."""

    amount_input: discord.ui.TextInput["Self"] = discord.ui.TextInput(
        label="金額",
        placeholder="請輸入轉帳金額",
        required=True,
    )

    note_input: discord.ui.TextInput["Self"] = discord.ui.TextInput(
        label="備註",
        placeholder="請輸入備註（選填）",
        required=False,
        max_length=200,
    )

    def __init__(
        self,
        panel: CompanyPanelView,
        *,
        target_id: int,
        target_name: str,
        target_type: str,  # "user" or "department"
        department: str | None = None,
    ) -> None:
        super().__init__(title=f"轉帳給 {target_name}")
        self.panel = panel
        self.target_id = target_id
        self.target_name = target_name
        self.target_type = target_type
        self.department = department

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if self.panel.current_company is None:
            await send_message_compat(interaction, content="請先選擇一家公司。", ephemeral=True)
            return

        # Parse amount
        try:
            amount = int(self.amount_input.value)
        except ValueError:
            await send_message_compat(interaction, content="金額必須為整數。", ephemeral=True)
            return

        if amount <= 0:
            await send_message_compat(interaction, content="轉帳金額必須為正整數。", ephemeral=True)
            return

        # Check balance
        balance_result = await self.panel.company_service.get_company_balance(
            guild_id=self.panel.guild_id,
            account_id=self.panel.current_company.account_id,
        )
        if isinstance(balance_result, Err):
            await send_message_compat(interaction, content="無法取得餘額資訊。", ephemeral=True)
            return

        balance = balance_result.value
        if amount > balance:
            await send_message_compat(interaction, content="公司帳戶餘額不足。", ephemeral=True)
            return

        # Resolve target ID for departments
        actual_target_id = self.target_id
        if self.target_type == "department" and self.department:
            # Import here to avoid circular dependency
            from src.bot.services.state_council_service import StateCouncilService

            actual_target_id = StateCouncilService.derive_department_account_id(
                self.panel.guild_id, self._get_department_name(self.department)
            )

        # Execute transfer using economy system

        from src.db import pool as db_pool
        from src.db.gateway.economy_transfers import EconomyTransferGateway

        pool: Any = db_pool.get_pool()
        gateway = EconomyTransferGateway()

        note = str(self.note_input.value).strip() if self.note_input.value else None

        try:
            async with pool.acquire() as connection:
                result = await gateway.transfer_currency(
                    connection,
                    guild_id=self.panel.guild_id,
                    initiator_id=self.panel.current_company.account_id,
                    target_id=actual_target_id,
                    amount=amount,
                    metadata={"reason": note} if note else {},
                )

            if isinstance(result, Err):
                await send_message_compat(
                    interaction, content=f"轉帳失敗：{result.error}", ephemeral=True
                )
                return

            # Success
            new_balance_result = await self.panel.company_service.get_company_balance(
                guild_id=self.panel.guild_id,
                account_id=self.panel.current_company.account_id,
            )
            new_balance = new_balance_result.value if isinstance(new_balance_result, Ok) else 0

            currency_display = _format_currency_display(self.panel.currency_config, amount)
            new_balance_display = _format_currency_display(self.panel.currency_config, new_balance)

            await send_message_compat(
                interaction,
                content=(
                    f"✅ 轉帳成功！\n"
                    f"已從 **{self.panel.current_company.name}** 轉帳 "
                    f"**{currency_display}** 給 **{self.target_name}**\n"
                    f"公司餘額：{new_balance_display}"
                ),
                ephemeral=True,
            )

            LOGGER.info(
                "company.transfer.success",
                guild_id=self.panel.guild_id,
                company_id=self.panel.current_company.id,
                target_id=actual_target_id,
                amount=amount,
            )

        except Exception as exc:
            LOGGER.exception(
                "company.transfer.failed",
                guild_id=self.panel.guild_id,
                error=str(exc),
            )
            await send_message_compat(interaction, content=f"轉帳失敗：{exc}", ephemeral=True)

    def _get_department_name(self, dept_value: str) -> str:
        """Convert department value to display name."""
        mapping = {
            "interior": "內政部",
            "finance": "財政部",
            "security": "國土安全部",
            "central_bank": "中央銀行",
            "justice": "法務部",
        }
        return mapping.get(dept_value, dept_value)
