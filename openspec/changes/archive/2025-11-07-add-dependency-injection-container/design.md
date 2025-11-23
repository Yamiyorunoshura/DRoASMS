## Context
目前系統中服務依賴管理存在以下問題：
1. 模組層級全域單例（`_TRANSFER_SERVICE`、`_BALANCE_SERVICE`）難以在測試中替換
2. 服務建構時依賴手動傳遞（如 `TransferService(pool, gateway=...)`），缺乏統一管理
3. 無法支援不同生命週期策略（如每次請求建立新實例、執行緒本地實例）
4. 測試時需要手動建立服務實例並傳遞依賴，程式碼重複

## Goals / Non-Goals

### Goals
- 提供統一的依賴管理容器，支援 Singleton、Factory、Thread-local 生命週期
- 類型安全的依賴解析（基於 Python 型別提示）
- 簡化測試（容器可替換，測試可使用 mock 容器）
- 保持向後相容（現有服務類別建構子不變）
- 最小化對現有程式碼的影響（漸進式遷移）

### Non-Goals
- 不引入外部 DI 框架（如 `dependency-injector`、`inject`），使用輕量級自實作
- 不強制所有模組立即遷移（允許漸進式採用）
- 不支援複雜的 AOP 或代理功能
- 不支援循環依賴自動解析（需手動處理）

## Decisions

### Decision: 輕量級自實作容器
**What**: 實作一個簡單的依賴注入容器，不引入外部框架。

**Why**:
- 專案原則偏好「簡單優先」，避免過度工程化
- 現有依賴結構相對簡單，不需要複雜框架功能
- 自實作可完全控制行為，符合專案風格

**Alternatives considered**:
- `dependency-injector`: 功能完整但過於複雜，學習曲線高
- `inject`: 較輕量但使用裝飾器，與專案風格不符
- 手動依賴傳遞: 現狀，但測試困難且缺乏統一管理

### Decision: 基於型別提示的解析
**What**: 使用 Python `typing` 模組的型別提示進行依賴解析。

**Why**:
- 符合 Python 3.13 型別系統最佳實踐
- 無需額外配置或裝飾器
- 與 `mypy` strict 模式相容

**Alternatives considered**:
- 字串鍵值註冊: 缺乏類型安全，容易出錯
- 裝飾器註冊: 增加程式碼複雜度，不符合專案風格

### Decision: 生命週期策略
**What**: 支援三種生命週期：Singleton（全域單例）、Factory（每次解析建立新實例）、Thread-local（執行緒本地單例）。

**Why**:
- Singleton: 適用於無狀態服務（如 Gateway）和資源（如 DB Pool）
- Factory: 適用於有狀態服務，每次請求需要新實例
- Thread-local: 適用於非同步環境中的執行緒隔離需求（目前專案較少使用，但預留擴展性）

**Alternatives considered**:
- 僅支援 Singleton: 過於簡化，無法滿足測試需求
- 支援更多生命週期（如 Request-scoped）: 過度設計，目前不需要

### Decision: 漸進式遷移策略
**What**: 不強制所有模組立即遷移，允許新舊方式並存。

**Why**:
- 降低遷移風險
- 允許逐步驗證容器實作
- 保持向後相容性

**Migration path**:
1. 實作容器核心功能
2. 遷移一個命令模組作為範例（如 `transfer.py`）
3. 逐步遷移其他命令模組
4. 最後移除舊的模組層級單例

## Risks / Trade-offs

### Risk: 過度工程化
**Mitigation**: 保持實作簡單，僅實作必要功能。遵循專案「簡單優先」原則。

### Risk: 型別解析複雜度
**Mitigation**: 使用 Python 標準 `typing` 模組，避免自定義型別系統。提供清晰的錯誤訊息。

### Risk: 測試替換機制複雜
**Mitigation**: 提供簡單的測試 fixture，允許測試中替換容器或註冊 mock 依賴。

### Trade-off: 自實作 vs 外部框架
- **自實作**: 完全控制、無外部依賴、學習成本低，但需要維護
- **外部框架**: 功能完整、社群支援，但增加依賴、學習曲線

選擇自實作符合專案「簡單優先」原則。

## Migration Plan

### Phase 1: 核心容器實作
1. 實作容器核心類別（`DependencyContainer`）
2. 實作生命週期管理（Singleton、Factory、Thread-local）
3. 實作型別解析機制
4. 單元測試覆蓋核心功能

### Phase 2: 整合到應用程式
1. 在 `main.py` 初始化容器
2. 註冊核心依賴（DB Pool、Gateway、Service）
3. 遷移一個命令模組作為範例（`transfer.py`）
4. 驗證功能正常

### Phase 3: 逐步遷移
1. 遷移其他命令模組（`balance.py`、`adjust.py`、`council.py`、`state_council.py`）
2. 更新測試 fixture 使用容器
3. 移除舊的模組層級單例

### Phase 4: 清理與優化
1. 移除未使用的舊程式碼
2. 更新文件說明容器使用方式
3. 效能驗證（確保無明顯開銷）

### Rollback Plan
- 保留舊的模組層級單例程式碼直到 Phase 4
- 可透過環境變數切換新舊方式（如 `USE_DI_CONTAINER=false`）

## Open Questions
- Thread-local 生命週期在 Discord bot 非同步環境中的實際需求？（目前預留，後續可根據需求調整）
- 是否需要支援依賴別名（alias）？（目前不需要，後續可擴展）
