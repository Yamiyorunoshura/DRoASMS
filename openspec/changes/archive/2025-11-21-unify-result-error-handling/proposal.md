# Change: 統一 Result<T,E> 錯誤處理實作與錯誤型別階層

## Why
上一個變更 `add-result-error-handling` 已在專案中導入 Rust 風格的 `Result<T,E>` 模式與錯誤型別階層，但目前實作仍處於「過渡狀態」：

- 存在多套 `Result` / `Error` 型別實作與相容層（例如 `src/common/result.py`、`src/common/errors.py`、`src/infra/result.py`、`src/infra/result_compat.py`），語意高度重疊。
- 服務層與指令層同時存在「Exception 版 service」與「Result 版 service」（例如 `StateCouncilService` vs `StateCouncilServiceResult`、`PermissionService` vs `PermissionService` Result 版），導致錯誤處理風格混雜。
- 呼叫端有的以 `try/except` 處理，有的檢查 `Ok/Err`，有的仍依賴舊的 `BaseError` 階層，與 `openspec/specs/error-handling` / `openspec/specs/infrastructure` 中要求的「統一 Result 模式」不完全一致。

這種情況增加了：

- 新功能開發的學習成本（開發者需要判斷應使用哪一套 Result / Error）
- 型別檢查與 IDE 導覽的混亂（相似名稱的錯誤型別分散在多個命名空間）
- 重構與除錯成本（同一 domain 需維護兩套錯誤處理邏輯）

本變更的目標是把「Result 錯誤處理」從「已導入、但仍有雙軌實作」收斂為「只有一套權威實作、明確的相容邊界」，讓後續開發可以假設：

- 專案只有一套 `Result<T,E>` / `AsyncResult<T,E>` 與 `Error` 階層。
- 所有服務與 gateway 都以該實作為標準，Exception 只在 UI 邊界或明確的 compat 區域出現。

## What Changes

### 1. 定義唯一權威的 Result / Error 實作
- 將 `src.infra.result` 明確定義為唯一權威的：
  - `Result[T, E]`、`Ok[T, E]`、`Err[T, E]`
  - `AsyncResult[T, E]`
  - `Error`、`DatabaseError`、`DiscordError`、`ValidationError`、`BusinessLogicError`、`PermissionDeniedError`、`SystemError`
- 新增（或整理）一個清晰的「公開介面」模組（可直接使用 `src.infra.result` 本身），做為所有上層程式碼匯入 `Result` / `Error` 的唯一入口。
- 明確將 `src.common.result` 和 `src.common.errors` 標記為「相容層」，不再新增新功能到這些模組。

### 2. 收斂錯誤型別階層與相容層邊界
- 統一錯誤階層，讓所有新的 domain error 一律繼承 `src.infra.result.Error`，而非 `BaseError` 或其他自訂根型別。
- 更新 `src/infra/db_errors.py` 等 mapping 工具，使其只產生 `infra.result.DatabaseError` / `SystemError`，避免產生第二套錯誤階層。
- 收斂 `src/infra/result_compat.py`、`src/common/result.py` 之使用範圍：
  - 只允許在明確標註為「legacy/compat」的路徑中使用（例如少量尚未改寫的舊 service）。
  - 新增明確的 deprecation 註解與紀錄工具，讓 CI / 靜態檢查可以發現新的相依。

### 3. 服務與 gateway 層錯誤處理統一
- 針對主要服務與治理 service（Transfer、Council、StateCouncil、Supreme Assembly、Suspect Management 等）建立清單：
  - 標記目前已使用 `Result` 模式的 method。
  - 找出仍以 `try/except` + Exception 回傳的 public API。
- 逐步將 public API 統一為：
  - 對外只暴露 `Result[T, ErrorSubtype]` 或 `AsyncResult[T, ErrorSubtype]`。
  - 內部若需要與舊 Exception API 整合，透過 `result_compat` 封裝，並明確註記為 legacy。
- gateway 層（`src/db/gateway/*`）的 DB 錯誤處理：
  - 若目前仍有直接 `raise asyncpg.PostgresError` 或其他 exception 的方法，改為透過 `map_asyncpg_error` 等工具轉成 `Result`。
  - 確保 spec `infrastructure` 中「資料庫操作錯誤 MUST 使用 Result 傳播」落實到主要 gateway。

### 4. 新增規範：禁止新增平行 Result 實作
- 在 `openspec/specs/error-handling` 新增／修改要求：
  - 專案內只能存在一套權威的 `Result<T,E>` / `AsyncResult<T,E>` 型別實作（`src.infra.result`）。
  - 其餘 module 若需要不同介面，只能透過 wrapper/adapter 呼叫該實作，不得再定義新的 `Ok` / `Err` class。
  - 相容層只允許包裝 canonical Result，不得引入新的錯誤語意。

### 5. 文件與開發者指南
- 更新 README / 開發者文件，說明：
  - 應從哪裡匯入 Result / Error。
  - 如何撰寫新的 service method 與 gateway method（範例以 Result 模式為主）。
  - 何處仍存在 compat 區域，以及未來預計移除時間點。

## Impact

### 受影響的規格
- `error-handling`：補強「唯一 Result / Error 實作」與「相容層使用邊界」的要求。
- `infrastructure`：強化服務層與 gateway 層必須使用 canonical Result / Error 的敘述（不再模糊容許雙軌）。

### 受影響的程式碼範圍（非完整清單）
- 錯誤處理核心與相容層：
  - `src/infra/result.py`
  - `src/infra/result_compat.py`
  - `src/common/result.py`
  - `src/common/errors.py`
  - `src/infra/db_errors.py`
- 主要 service / gateway：
  - `src/bot/services/*`（特別是成對存在的 `*Service` / `*ServiceResult`）
  - `src/db/gateway/*`
  - `src/infra/di/*`（Result 版容器註冊）
- 測試：
  - `tests/test_result.py`
  - 其他直接引用 `src.common.result` / `src.common.errors` 的測試

### 風險與緩解
- **風險：** 大量呼叫點需要調整匯入路徑與型別註記，若處理不慎可能造成型別錯誤或執行期行為改變。
  **緩解：**
  - 優先新增 re-export / alias，先讓舊路徑仍然工作，再漸進更新呼叫端。
  - 以 `rg` / Pyright / mypy 做搜尋與靜態檢查，確保沒有殘留的舊型別引用。
  - 分階段合併：先統一錯誤型別與 Result 實作，再處理 service 雙版本問題。
- **風險：** 相容層使用邊界不清晰，導致新程式碼不小心依賴 legacy API。
  **緩解：**
  - 在 compat 模組加入清楚的 deprecation 註解與 `MigrationTracker` 報表。
  - 可以視需要新增簡單的 lint 規則（或 CI 檢查），拒絕新檔案從 `src.common.result` 匯入。

## Out of Scope
- 不在本變更範圍內（但可能後續跟進）的項目：
  - 完全移除 `src/common/result.py` / `src/common/errors.py` 檔案（本變更只負責收斂與標記邊界）。
  - 大規模重寫所有治理與 UI 服務為純 Result 版（這部分可在後續 change 中細拆）。
  - 任何與 Discord UI / 互動文案相關的 UX 調整（除非是為了錯誤訊息格式對齊 spec）。

## Rollout / Migration Plan
1. **Phase 1：定義 canonical 實作與 re-export**
   - 在 `src.infra.result` 中確認與文件化所有公開型別。
   - 增加必要的別名或 re-export，確保 `src.common.result` 可以簡單轉呼叫 canonical 實作。
2. **Phase 2：更新核心呼叫端**
   - 逐步將 service / gateway / DI / commands 改為從 `src.infra.result` 匯入。
   - 在此階段保留 compat 模組，避免一次性大爆炸。
3. **Phase 3：限制 compat 使用範圍**
   - 標註 legacy 區域，並更新 `MigrationTracker` 報表。
   - 確保新檔案不再新增對 compat 的引用。
4. **Phase 4：驗證與清理**
   - 執行完整測試（單元、整合、performance）並追蹤錯誤率。
   - 若 compat 依賴已收斂到可接受範圍，再規劃後續 change 移除 legacy 模組。
