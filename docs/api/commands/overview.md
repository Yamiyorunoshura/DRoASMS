# 命令層 API 參考

DRoASMS 提供豐富的 Discord 斜杠命令（slash commands）來管理經濟系統與治理流程。本文件詳細說明每個命令的用途、參數、權限要求與使用範例。

## 命令概覽

### 經濟系統命令
- `/balance` - 查詢虛擬貨幣餘額
- `/transfer` - 轉移點數給其他成員或政府機構
- `/adjust` - 管理員調整成員點數
- `/history` - 查詢交易歷史記錄
- `/currency_config` - 設定伺服器貨幣名稱與圖示

### 治理系統命令
- `/council` - 常任理事會相關命令
- `/state_council` - 國務院治理相關命令
- `/supreme_assembly` - 最高人民會議相關命令

### 輔助命令
- `/help` - 顯示命令幫助資訊
- `/personal_panel` - 個人經濟管理面板

## 命令詳細說明

### `/balance`
查詢虛擬貨幣餘額，管理員可查詢其他成員的餘額。

**參數：**
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `member` | `User` | 否 | 要查詢的成員，預設為自己 |

**權限要求：**
- 一般成員：只能查詢自己的餘額
- 管理員（管理伺服器/系統管理員權限）：可查詢任何成員的餘額

**使用範例：**
```
/balance                    # 查詢自己的餘額
/balance @username          # 管理員查詢指定成員的餘額
```

**回應範例：**
```
🪙 你的餘額：1,250 金幣
💰 可用餘額：1,250 金幣
📊 帳戶狀態：正常
```

### `/transfer`
將虛擬貨幣轉移給伺服器中的其他成員或政府相關身分組。

**參數：**
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `target` | `User`/`Role` | 是 | 轉帳目標（成員、理事會身分組、國務院領袖身分組、部門領導人身分組） |
| `amount` | `Integer` | 是 | 轉帳金額（正整數） |
| `reason` | `String` | 否 | 轉帳原因（記錄在交易歷史中） |

**權限要求：**
- 所有成員均可使用（需符合轉帳限制）

**轉帳限制：**
- 餘額必須足夠
- 未在冷卻時間內（預設 5 分鐘）
- 未超過每日轉帳上限（若啟用）
- 不能轉帳給自己

**政府帳戶映射：**
- `@CouncilRole` → 理事會公共帳戶
- `@StateLeaderRole` → 國務院主帳戶
- `@DeptLeaderRole` → 對應部門帳戶

**使用範例：**
```
/transfer @username 100                         # 轉移 100 點給指定成員
/transfer @username 50 reason:午餐費用           # 轉移 50 點並添加備註
/transfer @CouncilRole 1000 reason:理事會補助     # 對理事會公共帳戶轉帳
/transfer @StateLeader 500 reason:國庫撥款        # 對國務院主帳戶轉帳
/transfer @DeptLeader 300 reason:部門預算         # 對對應部門帳戶轉帳
```

**回應範例：**
```
✅ 轉帳成功！
├─ 發送者：@sender
├─ 接收者：@receiver
├─ 金額：100 金幣
├─ 原因：午餐費用
└─ 新餘額：900 金幣
```

### `/adjust`
管理員調整成員點數（正數加值，負數扣點）。

**參數：**
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `target` | `User`/`Role` | 是 | 調整目標（成員或部門領導人身分組） |
| `amount` | `Integer` | 是 | 調整金額（可正可負） |
| `reason` | `String` | 是 | 調整原因（記錄在審計紀錄中） |

**權限要求：**
- 需要「管理伺服器」或「系統管理員」Discord 權限

**限制：**
- 不能使餘額變為負數
- 部門帳戶調整需對應部門領導人身分組

**使用範例：**
```
/adjust @username 100 reason:活動獎勵         # 給成員加值 100 點
/adjust @username -50 reason:違規懲罰         # 扣除成員 50 點
/adjust @DepartmentLeaderRole 500 reason:部門預算  # 調整部門政府帳戶餘額
```

**回應範例：**
```
📝 點數調整完成
├─ 目標：@member
├─ 調整：+100 金幣
├─ 原因：活動獎勵
├─ 操作者：@admin
└─ 新餘額：1,100 金幣
```

### `/history`
查詢虛擬貨幣的近期交易歷史。

**參數：**
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `member` | `User` | 否 | 要查詢的成員，預設為自己 |
| `limit` | `Integer` | 否 | 顯示筆數（1-50，預設 10） |
| `before` | `String` | 否 | ISO 8601 時間戳，僅顯示該時間點之前的紀錄 |

**權限要求：**
- 一般成員：只能查詢自己的歷史
- 管理員：可查詢任何成員的歷史

**使用範例：**
```
/history                   # 查看自己的交易歷史
/history @username         # 管理員查看指定成員的交易歷史
/history limit 20          # 顯示最近 20 筆記錄
/history before 2025-10-20T00:00:00Z  # 顯示指定時間之前的記錄
```

**回應範例：**
```
📜 交易歷史（最近 10 筆）
┌─ 2025-10-20 14:30:25 │ +100 │ 活動獎勵 (@admin)
├─ 2025-10-20 12:15:10 │ -50  │ 轉帳給 @friend (午餐)
├─ 2025-10-19 16:45:33 │ +500 │ 每日簽到
└─ ...（共 10 筆）
```

### `/currency_config`
設定該伺服器的貨幣名稱和圖示。

**參數：**
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `name` | `String` | 否 | 貨幣名稱（1-20 字元） |
| `icon` | `String` | 否 | 貨幣圖示（單一 emoji 或 Unicode 字元，最多 10 字元） |

**權限要求：**
- 需要「管理伺服器」或「系統管理員」Discord 權限

**說明：**
- 設定後，所有經濟相關指令和國務院面板都會使用新的貨幣名稱和圖示
- 未設定時，預設使用「點」作為貨幣名稱，無圖示
- 每個伺服器可以獨立設定自己的貨幣配置

**使用範例：**
```
/currency_config name:金幣 icon:🪙          # 設定貨幣名稱為「金幣」，圖示為 🪙
/currency_config name:點數                   # 僅更新貨幣名稱為「點數」
/currency_config icon:💰                     # 僅更新貨幣圖示為 💰
```

**回應範例：**
```
⚙️ 貨幣配置已更新
├─ 貨幣名稱：金幣
├─ 貨幣圖示：🪙
└─ 更新時間：2025-10-20 14:30:25
```

### `/council`
常任理事會相關命令，提供提案、投票與治理功能。

**子命令：**
- `/council config_role <role>` - 設定理事角色（管理員專用）
- `/council propose_transfer <target> <amount> <description> [attachment_url]` - 建立轉帳提案
- `/council cancel <proposal_id>` - 取消提案（無人投票前）
- `/council export <start> <end> <json|csv>` - 匯出提案記錄（管理員專用）
- `/council panel` - 開啟理事會面板

**權限要求：**
- `config_role`、`export`: 需要管理伺服器權限
- `propose_transfer`、`panel`: 需要理事角色
- `cancel`: 僅提案人且在無人投票前可取消

**提案流程：**
1. 理事發起轉帳提案
2. 系統鎖定當前理事名冊快照
3. 計算投票門檻：`floor(N/2) + 1`（N = 理事數）
4. 向所有理事發送投票請求（DM）
5. 72 小時內收集投票
6. 達到門檻則執行轉帳，否則逾時

**使用範例：**
```
/council config_role @理事會成員
/council propose_transfer @member 1000 社群活動補助
/council cancel prop_abc123
/council export 2025-10-01 2025-10-31 json
/council panel
```

### `/state_council`
國務院治理相關命令，管理部門配置、點數發行與轉帳。

**子命令：**
- `/state_council config_leader <leader|leader_role>` - 設定國務院領袖（管理員專用）
- `/state_council panel` - 開啟國務院面板

**權限要求：**
- `config_leader`: 需要管理伺服器權限
- `panel`: 需要國務院領袖角色

**面板功能：**
- 部門管理：設定各部門領導人身分組、稅率、發行上限
- 點數發行：向各部門發行點數
- 部門轉帳：各部門可向成員轉帳（透過政府帳戶）
- 匯出功能：匯出部門配置與發行記錄

**使用範例：**
```
/state_council config_leader @國務院領袖
/state_council panel
```

### `/supreme_assembly`
最高人民會議相關命令，最高層級的治理機制。

**子命令：**
- `/supreme_assembly panel` - 開啟最高人民會議面板

**權限要求：**
- 需要最高人民會議成員角色

### `/help`
顯示所有可用指令的說明，或查詢特定指令的詳細資訊。

**參數：**
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `command` | `String` | 否 | 要查詢的指令名稱 |

**使用範例：**
```
/help                    # 顯示所有可用指令列表
/help transfer           # 查詢 /transfer 指令的詳細說明
/help state_council      # 查詢國務院治理相關指令
```

### `/personal_panel`
開啟個人經濟管理面板，整合式介面管理個人經濟狀態。

**面板分頁：**
1. **首頁分頁**：查看當前餘額和帳戶狀態
2. **財產分頁**：查看完整交易歷史，支援分頁顯示
3. **轉帳分頁**：轉帳給使用者或政府機構

**使用範例：**
```
/personal_panel
```

## 命令實作技術細節

### 命令註冊
命令透過 Discord.py 的 `app_commands.CommandTree` 註冊：

```python
from discord import app_commands

@tree.command(name="balance", description="查詢虛擬貨幣餘額")
@app_commands.describe(member="要查詢的成員")
async def balance_command(
    interaction: discord.Interaction,
    member: discord.Member | None = None
) -> None:
    # 命令處理邏輯
    pass
```

### 權限檢查
權限檢查在命令處理層級與服務層級雙重驗證：

```python
async def balance_command(interaction: discord.Interaction, member: discord.Member | None):
    # Discord 權限檢查
    is_admin = interaction.user.guild_permissions.administrator

    # 服務層權限檢查
    result = await balance_service.get_balance_snapshot(
        guild_id=interaction.guild_id,
        requester_id=interaction.user.id,
        target_member_id=member.id if member else None,
        can_view_others=is_admin
    )
```

### 錯誤處理
命令錯誤透過 Discord 回應與日誌記錄：

```python
try:
    result = await transfer_service.transfer_currency(...)
    await interaction.response.send_message("✅ 轉帳成功！")
except InsufficientBalanceError:
    await interaction.response.send_message("❌ 餘額不足", ephemeral=True)
except TransferThrottleError:
    await interaction.response.send_message("⏳ 已達每日轉帳限制", ephemeral=True)
except Exception as e:
    logger.error("transfer_command_failed", error=e)
    await interaction.response.send_message("❌ 轉帳失敗，請稍後再試", ephemeral=True)
```

### 回應格式
命令回應使用嵌入式訊息（embed）與元件（components）：

```python
embed = discord.Embed(
    title="餘額查詢",
    description=f"**餘額：** {balance} {currency_icon}",
    color=discord.Color.green()
)
embed.set_footer(text=f"查詢時間：{datetime.now()}")

view = discord.ui.View()
view.add_item(discord.ui.Button(label="交易歷史", style=discord.ButtonStyle.secondary))

await interaction.response.send_message(embed=embed, view=view)
```

## 命令開發指南

### 新增命令步驟
1. 在 `src/bot/commands/` 下建立新命令模組
2. 定義命令函數與參數
3. 實作命令處理邏輯，呼叫對應服務
4. 在模組的 `register()` 函數中註冊命令
5. 在主程式中匯入並註冊模組
6. 編寫命令測試

### 命令模組結構
```python
# src/bot/commands/balance.py
import discord
from discord import app_commands

def register(tree: app_commands.CommandTree, *, container: DependencyContainer | None = None):
    @tree.command(name="balance", description="查詢虛擬貨幣餘額")
    @app_commands.describe(member="要查詢的成員")
    async def balance_command(
        interaction: discord.Interaction,
        member: discord.Member | None = None
    ) -> None:
        # 解析服務
        if container:
            balance_service = container.resolve(BalanceService)
        else:
            balance_service = BalanceService(...)

        # 命令邏輯
        # ...
```

### 測試命令
使用 Discord.py 測試框架模擬互動：

```python
import pytest
from unittest.mock import AsyncMock

async def test_balance_command():
    # 模擬 Interaction
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.user = AsyncMock(id=123, guild_permissions=...)
    interaction.guild_id = 456
    interaction.response = AsyncMock()

    # 執行命令
    await balance_command(interaction, member=None)

    # 驗證回應
    interaction.response.send_message.assert_called_once()
```

## 命令限制與配額

### 冷卻時間
- 轉帳命令：預設 5 分鐘冷卻
- 查詢命令：無冷卻時間
- 管理命令：無冷卻時間

### 每日限制
- 預設無限制（`TRANSFER_DAILY_LIMIT=0`）
- 可透過環境變數設定：`TRANSFER_DAILY_LIMIT=1000`

### 交易大小限制
- 單次轉帳：最大 1,000,000,000 點
- 歷史查詢：最多 50 筆
- 提案數量：同一伺服器最多 5 個進行中提案

## 相關文件

- [服務層 API](../services/overview.md)
- [經濟系統模組](../../modules/economy/overview.md)
- [治理系統模組](../../modules/governance/overview.md)
- [Discord.py 官方文檔](https://discordpy.readthedocs.io/)
