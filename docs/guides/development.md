# 開發者入門指南

本指南為 DRoASMS 專案的貢獻者提供完整的開發環境設置、工作流程與貢獻指引。無論您是第一次貢獻的新手還是有經驗的開發者，本文檔都將幫助您快速上手。

## 開發環境設置

### 前置需求
- **Python 3.13**（必須，專案已鎖定此版本）
- **Git**（版本控制）
- **PostgreSQL 15+**（或使用 Docker）
- **uv**（推薦）或 pip（最低要求）

### 1. 克隆專案
```bash
# 克隆專案到本地
git clone https://github.com/Yamiyorunoshura/DRoASMS.git
cd DRoASMS

# 確認分支
git branch -a
```

### 2. 設置 Python 環境
```bash
# 使用 uv 建立虛擬環境並安裝依賴（推薦）
uv sync

# 驗證安裝
uv run python --version  # 應顯示 Python 3.13.x
```

### 3. 配置開發環境變數
```bash
# 複製開發環境變數範本
cp .env.example .env.development

# 編輯開發配置
nano .env.development
```

**開發環境建議配置：**
```env
# 使用測試用的 Discord Token（可從 Discord 開發者後台取得測試用 Token）
DISCORD_TOKEN=你的測試用Token

# 使用本地 PostgreSQL 或 Docker 容器
DATABASE_URL=postgresql://bot:bot@127.0.0.1:5432/economy_dev

# 啟用開發模式功能
DEVELOPMENT_MODE=true
LOG_LEVEL=DEBUG

# 禁用生產環境限制（開發時方便測試）
TRANSFER_DAILY_LIMIT=0  # 無限制
TRANSFER_COOLDOWN_SECONDS=0  # 無冷卻
```

### 4. 設置資料庫（開發用）
```bash
# 方法 A：使用 Docker Compose（推薦）
docker compose up -d postgres

# 方法 B：手動建立開發資料庫
createdb economy_dev
psql -d economy_dev -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
```

### 5. 執行開發遷移
```bash
# 使用開發環境變數
export ENV_FILE=.env.development

# 執行資料庫遷移
uv run alembic upgrade head
```

## 開發工作流程

### 1. 創建功能分支
```bash
# 從 main 分支創建新分支
git checkout main
git pull --ff-only
git checkout -b feature/你的功能名稱

# 或修復錯誤
git checkout -b fix/錯誤描述
```

### 2. 安裝 pre-commit hooks
```bash
# 安裝並啟用 pre-commit hooks
make install-pre-commit

# 手動執行所有 hooks
make pre-commit-run
```

### 3. 本地開發循環
```bash
# 啟動開發伺服器（熱重載）
make dev

# 或手動啟動
uv run -m src.bot.main --env-file .env.development

# 在另一個終端運行測試
make test-unit
```

### 4. 提交更改
```bash
# 添加更改
git add .

# 提交（pre-commit 會自動運行）
git commit -m "feat: 新增功能描述"

# 推送到遠端
git push -u origin feature/你的功能名稱
```

## 測試指南

### 測試類型
專案包含多種測試類型，確保程式碼品質：

| 測試類型 | 目的 | 執行命令 |
|----------|------|----------|
| 單元測試 | 測試獨立單元功能 | `make test-unit` |
| 整合測試 | 測試模組間整合 | `make test-integration` |
| 合約測試 | 測試 API 合約 | `make test-contract` |
| 屬性測試 | 使用 Hypothesis 測試邊界案例 | `make test-property` |
| 性能測試 | 測試效能基準 | `make test-performance` |
| 資料庫測試 | 測試資料庫操作 | `make test-db` |

### 執行測試
```bash
# 執行所有測試（不含整合測試）
make test-all

# 執行特定測試套件
make test-unit
make test-integration
make test-economy
make test-council

# 使用測試容器（環境一致，推薦）
make test-container-unit
make test-container-all

# 生成覆蓋率報告
make coverage
```

### 編寫測試

#### 單元測試範例
```python
# tests/unit/test_balance_service.py
import pytest
from unittest.mock import AsyncMock

async def test_get_balance_snapshot_self(di_container, faker):
    """測試用戶查詢自己的餘額"""
    # 準備測試資料
    guild_id = faker.random_int()
    user_id = faker.random_int()

    # 解析服務
    service = di_container.resolve(BalanceService)

    # 執行測試
    result = await service.get_balance_snapshot(
        guild_id=guild_id,
        requester_id=user_id
    )

    # 驗證結果
    assert result.is_ok()
    snapshot = result.unwrap()
    assert snapshot.member_id == user_id
```

#### 整合測試範例
```python
# tests/integration/test_transfer_flow.py
async def test_transfer_flow(db_pool, faker):
    """測試完整的轉帳流程"""
    async with db_pool.acquire() as conn:
        # 初始化測試資料
        sender_id = faker.random_int()
        receiver_id = faker.random_int()
        guild_id = faker.random_int()

        # 建立服務
        service = TransferService(pool=db_pool)

        # 執行轉帳
        result = await service.transfer_currency(
            guild_id=guild_id,
            initiator_id=sender_id,
            target_id=receiver_id,
            amount=100,
            reason="測試轉帳",
            connection=conn
        )

        # 驗證結果
        assert isinstance(result, TransferResult)
        assert result.success
```

### 測試夾具 (Fixtures)
專案提供多個測試夾具，簡化測試編寫：

```python
# 使用內建夾具
async def test_with_fixtures(
    di_container,      # 依賴注入容器
    db_pool,          # 資料庫連線池
    faker,            # 假資料生成器
    event_loop,       # asyncio 事件循環
    mock_discord      # Discord API 模擬
):
    # 測試邏輯
    pass
```

## 程式碼品質

### 程式碼風格
專案使用嚴格的程式碼風格規範：

```bash
# 格式化程式碼
make format

# 檢查程式碼風格
make lint

# 自動修復可修復的問題
make lint-fix
```

### 類型檢查
採用 MyPy 和 Pyright 雙重類型檢查：

```bash
# MyPy 檢查
make type-check

# Pyright 檢查
make pyright-check

# 雙重檢查（CI 使用）
make ci-type-check
```

### 提交前檢查
pre-commit hooks 會自動執行以下檢查：
- 程式碼格式化（Black）
- 匯入排序（isort）
- 程式碼品質（Ruff）
- 類型檢查（MyPy, Pyright）
- 測試檢查（pytest）

## 依賴注入容器使用

### 容器註冊
服務在容器中註冊，支援三種生命週期：

```python
from src.infra.di.container import DependencyContainer
from src.infra.di.lifecycle import Lifecycle

# 建立容器
container = DependencyContainer()

# 註冊服務
container.register(BalanceService, lifecycle=Lifecycle.SINGLETON)
container.register(TransferService, lifecycle=Lifecycle.FACTORY)
```

### 服務解析
```python
# 解析服務
balance_service = container.resolve(BalanceService)
transfer_service = container.resolve(TransferService)

# 解析帶有依賴的服務（自動注入）
class MyService:
    def __init__(self, balance_service: BalanceService):
        self.balance_service = balance_service

container.register(MyService)
my_service = container.resolve(MyService)  # BalanceService 自動注入
```

### 測試中的容器使用
```python
async def test_with_container(di_container):
    # 替換真實服務為模擬物件
    mock_service = AsyncMock()
    di_container.register_instance(BalanceService, mock_service)

    # 解析服務會得到模擬物件
    service = di_container.resolve(BalanceService)
    assert service is mock_service
```

## 結果模式 (Result Pattern)

### 使用結果模式
專案使用 Result 模式進行錯誤處理：

```python
from src.infra.result import Ok, Err, Result

async def process_data() -> Result[Data, Error]:
    # 成功情況
    data = await fetch_data()
    if data:
        return Ok(data)

    # 失敗情況
    return Err(Error("資料獲取失敗"))

# 使用結果
result = await process_data()
if result.is_ok():
    data = result.unwrap()
    process(data)
else:
    error = result.unwrap_err()
    handle_error(error)
```

### 錯誤類型
```python
from src.infra.result import (
    Error,
    DatabaseError,
    BusinessLogicError,
    ValidationError,
)

# 建立自訂錯誤
class TransferError(Error):
    """轉帳相關錯誤"""
    pass

class InsufficientBalanceError(TransferError):
    """餘額不足錯誤"""
    pass
```

## Cython 編譯工作流程

### 編譯核心模組
```bash
# 編譯所有 Cython 模組
make cython-compile

# 測試編譯結果
make cython-test

# 清理編譯結果
make cython-clean

# 更新性能基準
make cython-baseline
```

### 開發時的編譯策略
```python
# 原始碼中直接匯入 Cython 模組
try:
    from src.cython_ext.economy_balance_models import BalanceSnapshot
except ImportError:
    # Fallback 到純 Python 實作
    from src.bot.models.economy_balance import BalanceSnapshot
```

## 除錯技巧

### 日誌記錄
```python
import structlog

logger = structlog.get_logger(__name__)

# 記錄不同等級的日誌
logger.debug("debug_message", data=data)
logger.info("info_message", user_id=user_id)
logger.warning("warning_message", error=error)
logger.error("error_message", exception=e)
```

### 除錯配置
```env
# .env.development
LOG_LEVEL=DEBUG
DEVELOPMENT_MODE=true
PYTHONASYNCIODEBUG=1
```

### 使用偵錯工具
```bash
# 使用 pdb 進行除錯
uv run python -m pdb -m src.bot.main

# 使用 ipdb（需要安裝）
import ipdb; ipdb.set_trace()
```

## 性能優化

### 性能測試
```bash
# 執行性能測試
make test-performance

# 生成性能報告
make performance-report

# 比較性能差異
make performance-compare
```

### 性能監控
```python
# 使用內建遙測監控
from src.infra.telemetry import metrics

# 記錄指標
metrics.counter("transfers.completed").inc()
metrics.histogram("transfer.amount").observe(amount)
metrics.gauge("active.users").set(active_count)
```

## 貢獻流程

### 1. 尋找貢獻機會
- 查看 [GitHub Issues](https://github.com/Yamiyorunoshura/DRoASMS/issues)
- 尋找標記為 `good-first-issue` 的項目
- 檢查專案的 [待辦事項](TODO.md)（如果存在）

### 2. 討論設計
- 在 Issue 中討論設計方案
- 對於重大變更，建立設計文件
- 尋求核心貢獻者的反饋

### 3. 實作功能
- 遵循現有程式碼風格與模式
- 編寫完整的測試套件
- 更新相關文件

### 4. 提交 Pull Request
```bash
# 確保所有檢查通過
make ci-full

# 提交 PR
gh pr create --title "功能描述" --body "詳細說明"
```

### 5. 程式碼審查
- 回應審查意見
- 根據反饋修改程式碼
- 確保 CI 檢查通過

## 常見問題

### Q: 測試時如何模擬 Discord API？
```python
# 使用 mock_discord fixture
async def test_discord_command(mock_discord):
    interaction = mock_discord.Interaction()
    interaction.user = mock_discord.User(id=123)
    # ... 測試邏輯
```

### Q: 如何新增環境變數？
1. 在 `src/config/settings.py` 中定義設定類別
2. 在 `.env.example` 中添加範例
3. 在相關文件中說明用途

### Q: 資料庫遷移失敗怎麼辦？
```bash
# 檢查遷移狀態
uv run alembic current

# 降級遷移
uv run alembic downgrade -1

# 重新執行遷移
uv run alembic upgrade head
```

### Q: 如何新增依賴套件？
```bash
# 使用 uv 新增依賴
uv add package-name

# 新增開發依賴
uv add --dev package-name

# 更新 lock 檔案
uv lock
```

## 學習資源

### 專案內部資源
- [架構概述](../architecture/overview.md) - 系統整體設計
- [API 參考](../api/overview.md) - 各層級介面說明
- [模組說明](../modules/README.md) - 功能模組詳細說明

### 外部資源
- [Discord.py 文檔](https://discordpy.readthedocs.io/) - Discord API 客戶端
- [Pydantic 文檔](https://docs.pydantic.dev/) - 資料驗證與設定管理
- [asyncpg 文檔](https://magicstack.github.io/asyncpg/) - 非同步 PostgreSQL 驅動
- [uv 文檔](https://docs.astral.sh/uv/) - Python 套件管理器

## 尋求幫助

如果您在開發過程中遇到問題：

1. **查閱文件**：本指南與其他專案文件
2. **檢查測試**：相關功能的測試範例
3. **搜索 Issue**：查看是否有類似問題
4. **提出問題**：在 GitHub Discussions 提問
5. **聯繫維護者**：透過 Issue 或 Discussion 聯繫

## 下一步

- [貢獻指南](../contributing/README.md) - 完整的貢獻流程與規範
- [部署指南](deployment.md) - 生產環境部署指南
- [架構決策記錄](../architecture/decisions.md) - 重要的架構決策與原因
