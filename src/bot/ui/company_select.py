"""Shared company selection UI components.

Provides reusable company selection UI elements for transfer functionality
across all governance panels.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable, Sequence, cast

import discord
import structlog

from src.bot.interaction_compat import send_message_compat
from src.bot.services.company_service import CompanyService
from src.db.gateway.company import CompanyGateway
from src.db.pool import get_pool
from src.infra.result import Err

if TYPE_CHECKING:
    from src.cython_ext.state_council_models import Company

LOGGER = structlog.get_logger(__name__)


async def get_active_companies(guild_id: int) -> list["Company"]:
    """Fetch all active companies in a guild.

    Args:
        guild_id: Discord guild ID

    Returns:
        List of active companies (with valid licenses)
    """
    try:
        pool = get_pool()
        service = CompanyService(pool)
        result = await service.list_guild_companies(guild_id=guild_id, page=1, page_size=100)
        if isinstance(result, Err):
            LOGGER.warning(
                "company_select.fetch.error",
                guild_id=guild_id,
                error=str(result.error),
            )
            return []

        company_list = result.value
        # Filter to only active companies (license_status == 'active')
        active = [c for c in company_list.companies if c.license_status == "active"]
        return active
    except Exception as exc:
        LOGGER.warning(
            "company_select.fetch.exception",
            guild_id=guild_id,
            error=str(exc),
        )
        return []


def build_company_select_options(companies: Sequence["Company"]) -> list[discord.SelectOption]:
    """Build Discord select options from company list.

    Args:
        companies: List of companies

    Returns:
        List of SelectOption for Discord select menu
    """
    options: list[discord.SelectOption] = []
    for company in companies[:25]:  # Discord limit
        options.append(
            discord.SelectOption(
                label=company.name,
                value=str(company.id),
                description=f"帳戶 ID: {company.account_id}",
                emoji="🏢",
            )
        )
    return options


class CompanySelectView(discord.ui.View):
    """Generic company selection view.

    This view provides a company selection dropdown that can be reused
    across different panels (personal, state council, council, supreme assembly).
    """

    def __init__(
        self,
        *,
        guild_id: int,
        on_company_selected: Callable[
            [discord.Interaction, "Company"],
            Awaitable[None],
        ],
        timeout: float = 300.0,
    ) -> None:
        """Initialize company select view.

        Args:
            guild_id: Discord guild ID to fetch companies from
            on_company_selected: Callback when a company is selected
            timeout: View timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.guild_id = guild_id
        self.on_company_selected = on_company_selected
        self._companies: dict[int, "Company"] = {}

    async def setup(self) -> bool:
        """Fetch companies and setup the select menu.

        Returns:
            True if companies are available, False otherwise
        """
        companies = await get_active_companies(self.guild_id)
        if not companies:
            return False

        self._companies = {c.id: c for c in companies}
        options = build_company_select_options(companies)

        select: discord.ui.Select[Any] = discord.ui.Select(
            placeholder="🏢 選擇公司...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="company_select_menu",
        )
        select.callback = self._on_select
        self.add_item(select)
        return True

    async def _on_select(self, interaction: discord.Interaction) -> None:
        """Handle company selection."""
        if not interaction.data:
            await send_message_compat(interaction, content="請選擇一家公司。", ephemeral=True)
            return

        data = cast(dict[str, Any], interaction.data)
        values = cast(list[str] | None, data.get("values"))
        if not values:
            await send_message_compat(interaction, content="請選擇一家公司。", ephemeral=True)
            return

        try:
            company_id = int(values[0])
        except ValueError:
            await send_message_compat(interaction, content="選項格式錯誤。", ephemeral=True)
            return

        company = self._companies.get(company_id)
        if company is None:
            await send_message_compat(interaction, content="找不到指定的公司。", ephemeral=True)
            return

        await self.on_company_selected(interaction, company)


def derive_company_account_id(company_id: int) -> int:
    """Derive the account ID for a company.

    Uses the same formula as CompanyGateway.derive_account_id but without
    requiring guild_id (since guild_id is no longer used in the calculation).

    Args:
        company_id: The company's database ID

    Returns:
        The derived account ID (9_600_000_000_000_000 + company_id)
    """
    return CompanyGateway.derive_account_id(0, company_id)
