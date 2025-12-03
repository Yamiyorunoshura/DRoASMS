# 服務層 API 概述

服務層是 DRoASMS 專案的核心業務邏輯層，負責處理經濟系統與治理系統的所有業務規則、驗證邏輯與協調操作。本文件說明服務層的設計模式、通用介面與主要服務類別。

## 設計模式

### 依賴注入 (Dependency Injection)
所有服務都透過依賴注入容器管理，支援三種生命週期：
- `SINGLETON`: 單例模式，整個應用共享一個實例
- `FACTORY`: 工廠模式，每次解析時創建新實例
- `THREAD_LOCAL`: 執行緒局部模式，每個執行緒一個實例

```python
from src.infra.di.container import DependencyContainer
from src.infra.di.lifecycle import Lifecycle

# 建立容器
container = DependencyContainer()

# 註冊服務
container.register(BalanceService, lifecycle=Lifecycle.SINGLETON)

# 解析服務
balance_service = container.resolve(BalanceService)
```

### 結果模式 (Result Pattern)
統一錯誤處理機制，避免異常傳播，提供類型安全的錯誤處理：

```python
from src.infra.result import Ok, Err, Result

async def process_transfer() -> Result[TransferResult, TransferError]:
    result = await transfer_service.transfer_currency(...)
    if result.is_err():
        error = result.unwrap_err()
        # 處理錯誤
        return Err(error)
    # 處理成功
    return Ok(result.unwrap())
```

### 雙模式合約 (Dual-Mode Contract)
為同時支援舊有程式碼與新的 Result 模式，許多服務提供雙模式介面：

```python
# 模式 1: 傳統異常模式（提供 connection 參數）
async with pool.acquire() as conn:
    snapshot = await balance_service.get_balance_snapshot(
        guild_id=123,
        requester_id=456,
        connection=conn  # 明確提供 connection，使用異常模式
    )

# 模式 2: Result 模式（不提供 connection 參數）
result = await balance_service.get_balance_snapshot(
    guild_id=123,
    requester_id=456
    # 不提供 connection，返回 Result 類型
)
if result.is_ok():
    snapshot = result.unwrap()
```

## 服務類別概覽

### 經濟系統服務

#### BalanceService
餘額查詢與交易歷史服務，提供權限檢查與分頁功能。

**主要方法：**
- `get_balance_snapshot()`: 取得餘額快照
- `get_history()`: 取得交易歷史分頁

**使用範例：**
```python
# 取得餘額快照
snapshot = await balance_service.get_balance_snapshot(
    guild_id=guild_id,
    requester_id=user_id,
    target_member_id=target_id,
    can_view_others=is_admin
)

# 取得交易歷史
history_page = await balance_service.get_history(
    guild_id=guild_id,
    requester_id=user_id,
    limit=20,
    cursor=previous_cursor
)
```

#### TransferService
點數轉移服務，支援同步模式與事件池模式。

**主要方法：**
- `transfer_currency()`: 執行點數轉移
- `get_transfer_status()`: 查詢轉移狀態（事件池模式）

**使用範例：**
```python
# 同步轉帳模式
transfer_result = await transfer_service.transfer_currency(
    guild_id=guild_id,
    initiator_id=sender_id,
    target_id=receiver_id,
    amount=100,
    reason="午餐費用"
)

# 事件池模式（返回 transfer_id）
transfer_id = await transfer_service.transfer_currency(
    guild_id=guild_id,
    initiator_id=sender_id,
    target_id=receiver_id,
    amount=100,
    reason="午餐費用"
)
# 可透過 transfer_id 查詢狀態
status = await transfer_service.get_transfer_status(transfer_id=transfer_id)
```

#### AdjustmentService
管理員點數調整服務，支援加值與扣點操作。

**主要方法：**
- `adjust_balance()`: 調整成員點數
- `get_adjustment_history()`: 取得調整記錄

**使用範例：**
```python
# 調整點數
adjustment_result = await adjustment_service.adjust_balance(
    guild_id=guild_id,
    admin_id=admin_id,
    target_id=member_id,
    amount=50,  # 正數加值，負數扣點
    reason="活動獎勵"
)
```

#### CurrencyConfigService
伺服器貨幣配置服務，管理貨幣名稱與圖示。

**主要方法：**
- `get_currency_config()`: 取得貨幣配置
- `set_currency_config()`: 設定貨幣配置

**使用範例：**
```python
# 取得配置
config = await currency_config_service.get_currency_config(guild_id=guild_id)

# 更新配置
await currency_config_service.set_currency_config(
    guild_id=guild_id,
    name="金幣",
    icon="🪙"
)
```

#### TransferEventPool
轉帳事件池服務，處理異步轉帳與重試邏輯。

**主要方法：**
- `enqueue_transfer()`: 加入轉帳到事件池
- `process_pending_transfers()`: 處理待處理轉帳
- `get_queue_stats()`: 取得隊列統計

### 治理系統服務

#### CouncilService
常任理事會治理服務，處理提案、投票與決策執行。

**主要方法：**
- `create_proposal()`: 建立轉帳提案
- `vote_on_proposal()`: 對提案投票
- `cancel_proposal()`: 取消提案
- `get_proposal_status()`: 取得提案狀態

**使用範例：**
```python
# 建立提案
proposal = await council_service.create_proposal(
    guild_id=guild_id,
    proposer_id=council_member_id,
    target_id=recipient_id,
    amount=1000,
    description="理事會補助"
)

# 進行投票
vote_result = await council_service.vote_on_proposal(
    guild_id=guild_id,
    proposal_id=proposal.id,
    voter_id=member_id,
    vote="agree"  # agree, disagree, abstain
)
```

#### StateCouncilService
國務院治理服務，管理部門配置、點數發行與部門轉帳。

**主要方法：**
- `configure_department()`: 配置部門設定
- `issue_currency()`: 向部門發行點數
- `department_transfer()`: 部門轉帳
- `get_department_stats()`: 取得部門統計

#### SupremeAssemblyService
最高人民會議治理服務，最高層級的治理機制。

#### JusticeGovernance
司法治理服務，處理爭議解決與仲裁。

## 錯誤處理

### 錯誤類型階層
```
Error (基底)
├── DatabaseError (資料庫錯誤)
├── BusinessLogicError (業務邏輯錯誤)
├── ValidationError (驗證錯誤)
└── 服務特定錯誤
    ├── BalanceError
    │   └── BalancePermissionError
    ├── TransferError
    │   ├── TransferValidationError
    │   ├── InsufficientBalanceError
    │   └── TransferThrottleError
    └── CouncilError
        ├── ProposalCreationError
        └── VotingError
```

### 錯誤處理範例
```python
from src.infra.result import Err, Ok, Result
from src.bot.services.transfer_service import (
    TransferService,
    InsufficientBalanceError,
    TransferThrottleError,
    TransferValidationError,
)

async def handle_transfer(
    transfer_service: TransferService,
    **transfer_args
) -> Result[TransferResult, str]:
    try:
        result = await transfer_service.transfer_currency(**transfer_args)
        return Ok(result)
    except InsufficientBalanceError as e:
        return Err("餘額不足")
    except TransferThrottleError as e:
        return Err("已達每日轉帳限制")
    except TransferValidationError as e:
        return Err(f"驗證失敗: {e}")
    except Exception as e:
        return Err(f"未知錯誤: {e}")
```

## 測試策略

### 單元測試
使用依賴注入容器替換實際依賴，測試服務邏輯：

```python
import pytest
from unittest.mock import AsyncMock

async def test_balance_service(di_container):
    # 替換資料庫閘道
    mock_gateway = AsyncMock()
    di_container.register_instance(EconomyQueryGateway, mock_gateway)

    # 解析服務
    service = di_container.resolve(BalanceService)

    # 設定 mock 行為
    mock_gateway.fetch_balance.return_value = Ok(mock_balance_record)

    # 測試服務方法
    result = await service.get_balance_snapshot(...)
    assert result.is_ok()
```

### 整合測試
使用真實資料庫連線測試服務與資料庫的交互：

```python
async def test_transfer_service_integration(db_pool):
    async with db_pool.acquire() as conn:
        service = TransferService(pool=db_pool)

        # 執行實際轉帳
        result = await service.transfer_currency(
            guild_id=test_guild_id,
            initiator_id=sender_id,
            target_id=receiver_id,
            amount=100,
            connection=conn
        )

        # 驗證結果
        assert isinstance(result, TransferResult)
        assert result.success
```

## 性能考量

### Cython 編譯
核心服務方法已透過 Cython 編譯優化，提供顯著的性能提升：

```python
# 編譯後的模組位於 src/cython_ext/
from src.cython_ext.economy_balance_models import BalanceSnapshot, make_balance_snapshot
from src.cython_ext.economy_transfer_models import TransferResult, transfer_result_from_procedure
```

### 非同步處理
所有服務方法都使用 `async/await` 語法，支援高併發處理：

```python
# 支援並行處理多個請求
tasks = [
    balance_service.get_balance_snapshot(guild_id=guild_id, requester_id=user_id)
    for user_id in user_ids
]
results = await asyncio.gather(*tasks)
```

### 連線池管理
服務自動管理資料庫連線池，避免頻繁建立連線開銷：

```python
class BalanceService:
    def __init__(self, pool: PoolProtocol):
        self._pool = pool  # 重用連線池

    async def get_balance_snapshot(self, ...):
        async with self._pool.acquire() as conn:
            # 使用連線池中的連線
            return await self._gateway.fetch_balance(conn, ...)
```

## 擴展指南

### 新增服務步驟
1. 在 `src/bot/services/` 下建立新服務類別
2. 遵循依賴注入模式，透過建構子接收依賴
3. 實作 Result 模式或雙模式合約
4. 在 `src/infra/di/container.py` 中註冊服務
5. 編寫單元測試與整合測試
6. 更新本文檔反映新增服務

### 服務設計原則
1. **單一職責**: 每個服務專注於單一業務領域
2. **明確介面**: 公開方法提供清晰的參數與回傳類型
3. **錯誤處理**: 使用 Result 模式或定義明確的異常類型
4. **可測試性**: 支援依賴替換，便於單元測試
5. **性能意識**: 考慮併發處理與資源管理

## 相關文件

- [依賴注入容器](../../modules/infrastructure/di-container.md)
- [結果模式](../../modules/infrastructure/result-pattern.md)
- [資料庫閘道層](../gateway/overview.md)
- [命令層 API](../commands/overview.md)
