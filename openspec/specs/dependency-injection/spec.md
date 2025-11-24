# dependency-injection Specification

## Purpose
TBD - created by archiving change add-dependency-injection-container. Update Purpose after archive.
## Requirements
### Requirement: 依賴注入容器核心功能
系統 SHALL 提供一個依賴注入容器，支援註冊與解析依賴。

#### Scenario: 註冊依賴
- **WHEN** 開發者呼叫容器的 `register` 方法註冊一個類型
- **THEN** 容器記錄該類型的註冊資訊（實作類別、生命週期策略）
- **AND** 註冊成功後可透過 `resolve` 方法解析該類型

#### Scenario: 解析已註冊的依賴
- **WHEN** 開發者呼叫容器的 `resolve` 方法解析已註冊的類型
- **THEN** 容器根據生命週期策略返回適當的實例
- **AND** 解析的實例類型符合註冊的類型提示

#### Scenario: 解析未註冊的依賴
- **WHEN** 開發者嘗試解析未註冊的類型
- **THEN** 容器拋出清楚的錯誤訊息（如 `DependencyNotRegisteredError`）
- **AND** 錯誤訊息包含未註冊的類型名稱

### Requirement: Singleton 生命週期
系統 SHALL 支援 Singleton 生命週期，確保同一類型在容器中只有一個實例。

#### Scenario: Singleton 實例重用
- **WHEN** 開發者註冊一個類型為 Singleton 生命週期
- **AND** 多次呼叫 `resolve` 解析該類型
- **THEN** 每次解析返回相同的實例
- **AND** 實例僅在建構時建立一次

#### Scenario: Singleton 適用於無狀態服務
- **WHEN** 開發者註冊 Gateway 或無狀態 Service 為 Singleton
- **THEN** 容器重用同一實例，減少記憶體開銷
- **AND** 實例可安全地在多個請求間共享

### Requirement: Thread-Safe Singleton Resolution
The dependency injection container SHALL provide thread-safe singleton resolution that prevents deadlocks when factories recursively resolve other singleton dependencies.

#### Scenario: Singleton with singleton dependency
- **WHEN** a singleton service's factory function resolves another singleton dependency
- **THEN** the resolution completes without deadlock
- **AND** both singletons are correctly instantiated and cached

#### Scenario: Circular dependency detection with singletons
- **WHEN** circular dependencies are detected during singleton resolution
- **THEN** a RuntimeError is raised with a clear cycle description
- **AND** no deadlock occurs during the detection process

#### Scenario: Concurrent singleton resolution
- **WHEN** multiple threads simultaneously resolve the same singleton
- **THEN** only one instance is created
- **AND** all threads receive the same instance
- **AND** no deadlock occurs

### Requirement: Factory 生命週期
系統 SHALL 支援 Factory 生命週期，每次解析時建立新實例。

#### Scenario: Factory 建立新實例
- **WHEN** 開發者註冊一個類型為 Factory 生命週期
- **AND** 多次呼叫 `resolve` 解析該類型
- **THEN** 每次解析返回不同的新實例
- **AND** 實例在每次解析時建立

#### Scenario: Factory 適用於有狀態服務
- **WHEN** 開發者註冊有狀態的 Service 為 Factory
- **THEN** 每次請求獲得獨立實例，避免狀態污染
- **AND** 測試時可獨立驗證每個實例的行為

### Requirement: Thread-local 生命週期
系統 SHALL 支援 Thread-local 生命週期，每個執行緒維護獨立的單例實例。

#### Scenario: Thread-local 執行緒隔離
- **WHEN** 開發者註冊一個類型為 Thread-local 生命週期
- **AND** 在不同執行緒中解析該類型
- **THEN** 每個執行緒獲得獨立的實例
- **AND** 同一執行緒內多次解析返回相同實例

#### Scenario: Thread-local 適用於執行緒本地資源
- **WHEN** 開發者註冊執行緒本地資源為 Thread-local
- **THEN** 每個執行緒維護獨立的資源實例
- **AND** 避免執行緒間的資源競爭

### Requirement: 類型安全的依賴解析
系統 SHALL 基於 Python 型別提示進行依賴解析，提供類型安全保證。

#### Scenario: 從建構子推斷依賴
- **WHEN** 開發者註冊一個服務類型
- **AND** 該服務的建構子包含型別提示參數
- **THEN** 容器自動從建構子參數推斷所需依賴
- **AND** 解析時自動注入已註冊的依賴

#### Scenario: 型別提示驗證
- **WHEN** 容器解析依賴時
- **THEN** 容器驗證註冊的實作類型符合要求的類型提示
- **AND** 類型不匹配時拋出清楚的錯誤訊息

#### Scenario: 可選依賴處理
- **WHEN** 服務建構子包含可選參數（`Optional[T]` 或預設值）
- **THEN** 容器僅在依賴已註冊時注入
- **AND** 未註冊時使用預設值或 `None`

### Requirement: 循環依賴檢測
系統 SHALL 檢測並報告循環依賴錯誤。

#### Scenario: 循環依賴錯誤
- **WHEN** 服務 A 依賴服務 B，服務 B 依賴服務 A
- **AND** 開發者嘗試解析服務 A
- **THEN** 容器檢測到循環依賴
- **AND** 拋出清楚的錯誤訊息（如 `CircularDependencyError`）
- **AND** 錯誤訊息包含循環依賴的路徑

### Requirement: 容器在應用程式中的初始化
系統 SHALL 在應用程式啟動時初始化容器並註冊核心依賴。

#### Scenario: 容器初始化
- **WHEN** 應用程式啟動（`main.py`）
- **THEN** 建立容器實例
- **AND** 註冊核心基礎設施依賴（DB Pool、Logger）
- **AND** 註冊所有 Gateway 依賴
- **AND** 註冊所有 Service 依賴

#### Scenario: 容器生命週期管理
- **WHEN** 應用程式關閉
- **THEN** 容器正確清理資源（如關閉 Singleton 實例的連線）
- **AND** 避免資源洩漏

### Requirement: 命令模組使用容器
系統 SHALL 允許命令模組從容器解析服務依賴。

#### Scenario: 命令模組解析服務
- **WHEN** 命令模組需要服務實例（如 `TransferService`）
- **THEN** 命令模組從容器解析服務
- **AND** 不再使用模組層級全域單例
- **AND** 解析的服務實例正確運作

#### Scenario: Result 版服務註冊順序
- **WHEN** 執行 `bootstrap_result_container()`
- **THEN** 容器 MUST 先註冊傳統服務，再由 `ResultContainer` 註冊 Result 版 `CouncilServiceResult`/`StateCouncilServiceResult`
- **AND** `PermissionService` MUST 於 Result 版服務註冊後建立，確保其依賴的 Result 服務可被解析

#### Scenario: 命令註冊時傳遞容器
- **WHEN** 命令模組註冊到命令樹（`CommandTree`）
- **THEN** 命令模組接收容器參數
- **AND** 命令模組使用容器建立命令處理函式

### Requirement: 測試中的容器替換
系統 SHALL 允許測試中替換容器或註冊 mock 依賴。

#### Scenario: 測試使用 mock 容器
- **WHEN** 測試需要 mock 服務依賴
- **THEN** 測試可建立新的容器實例
- **AND** 測試可註冊 mock 實作取代真實服務
- **AND** 測試使用 mock 容器執行被測程式碼

#### Scenario: 測試 fixture 提供容器
- **WHEN** 測試使用容器相關 fixture
- **THEN** fixture 提供預設配置的容器
- **AND** 測試可覆寫特定依賴註冊
- **AND** 測試結束時容器正確清理

#### Scenario: 向後相容的測試
- **WHEN** 現有測試尚未遷移到使用容器
- **THEN** 測試仍可正常執行（使用舊的服務實例化方式）
- **AND** 漸進式遷移不影響現有測試
