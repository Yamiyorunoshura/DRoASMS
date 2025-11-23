## Why
目前系統使用模組層級的全域單例（如 `_TRANSFER_SERVICE`、`_BALANCE_SERVICE`）管理服務依賴，導致測試時難以替換依賴、缺乏統一的依賴管理機制，且無法支援不同的生命週期（Singleton、Factory、Thread-local）。引入依賴注入容器可統一管理依賴、簡化測試（容器可替換）、提供類型安全的依賴解析，並支援多種生命週期策略。

## What Changes
- **新增**：依賴注入容器核心介面與實作
- **新增**：支援 Singleton、Factory、Thread-local 生命週期
- **新增**：類型安全的依賴解析（基於 Python 型別提示）
- **修改**：服務實例化方式從模組層級單例改為容器解析
- **修改**：命令模組改為從容器取得服務實例
- **新增**：測試用容器替換機制

## Impact
- Affected specs: 新增 `dependency-injection` capability
- Affected code:
  - `src/bot/commands/*` - 命令模組的服務取得方式
  - `src/bot/services/*` - 服務類別（保持建構子注入，但由容器管理）
  - `src/bot/main.py` - 容器初始化與生命週期管理
  - `tests/**` - 測試 fixture 與容器替換
