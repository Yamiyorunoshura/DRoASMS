# API 參考文件

本目錄包含 DRoASMS 專案各層級的 API 參考文件，包括服務層、命令層、資料庫閘道層與事件系統的介面說明。

## 文件結構

```
api/
├── services/          # 業務邏輯服務層 API
├── commands/          # Discord 命令層 API
├── gateway/           # 資料庫閘道層 API
├── events/            # 事件系統 API
└── infrastructure/    # 基礎設施層 API
```

## 服務層 API (`services/`)

業務邏輯服務層提供核心的經濟與治理功能：

- **經濟系統服務**：
  - `BalanceService` - 餘額查詢與帳戶管理
  - `TransferService` - 點數轉移與驗證邏輯
  - `AdjustmentService` - 管理員點數調整
  - `CurrencyConfigService` - 貨幣配置管理
  - `TransferEventPool` - 異步轉帳處理池

- **治理系統服務**：
  - `CouncilService` - 常任理事會治理
  - `StateCouncilService` - 國務院治理
  - `SupremeAssemblyService` - 最高人民會議治理
  - `JusticeGovernance` - 司法治理

## 命令層 API (`commands/`)

Discord 斜杠命令的介面定義與處理邏輯：

- **經濟命令**：
  - `/balance` - 查詢餘額
  - `/transfer` - 轉移點數
  - `/adjust` - 調整點數（管理員）
  - `/history` - 交易歷史查詢
  - `/currency_config` - 貨幣配置（管理員）

- **治理命令**：
  - `/council` - 常任理事會相關命令
  - `/state_council` - 國務院相關命令
  - `/supreme_assembly` - 最高人民會議相關命令

## 資料庫閘道層 API (`gateway/`)

資料庫存取層的介面定義，採用閘道模式封裝 SQL 操作：

- **經濟系統閘道**：
  - `economy_queries` - 餘額與帳戶查詢
  - `economy_transfers` - 轉帳記錄操作
  - `economy_adjustments` - 調整記錄操作
  - `economy_configuration` - 配置資料操作
  - `pending_transfers` - 待處理轉帳操作

- **治理系統閘道**：
  - `council_governance` - 理事會提案與投票
  - `state_council_governance` - 國務院部門管理
  - `supreme_assembly_governance` - 最高人民會議記錄

## 事件系統 API (`events/`)

事件驅動架構的事件定義與處理器介面：

- **事件類型**：
  - `TransferEvent` - 轉帳相關事件
  - `CouncilProposalEvent` - 理事會提案事件
  - `StateCouncilEvent` - 國務院相關事件
  - `SystemEvent` - 系統級事件

- **事件處理器**：
  - 事件訂閱與發布介面
  - 處理器註冊機制
  - 異步事件處理流程

## 基礎設施層 API (`infrastructure/`)

共享技術基礎設施的介面定義：

- **依賴注入容器**：
  - `DependencyContainer` - 容器介面
  - `Lifecycle` - 生命週期枚舉
  - 服務註冊與解析方法

- **結果模式**：
  - `Result` - 結果類型定義
  - `Success` / `Failure` - 成功與失敗結果
  - 錯誤類型與處理工具

- **配置管理**：
  - `BotSettings` - 機器人設定
  - `PoolConfig` - 資料庫連線池設定
  - 環境變數驗證與載入

## 使用指南

1. **服務層使用**：透過依賴注入容器解析服務實例
2. **命令層使用**：Discord 命令自動註冊與處理
3. **閘道層使用**：業務服務透過閘道存取資料庫
4. **事件系統使用**：訂閱感興趣的事件，發布業務事件

## 類型提示與文檔

所有 API 都包含完整的類型提示與文檔字串，可使用 IDE 的自動完成與文檔查看功能，或執行 `uv run python -m pydoc <module>` 查看詳細文檔。
