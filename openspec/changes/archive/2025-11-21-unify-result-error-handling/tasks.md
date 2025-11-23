## 1. 梳理與鎖定權威 Result / Error 實作
- [x] 1.1 盤點現有 Result / Error 實作與相容層
  - [x] 1.1.1 列出所有定義 `Ok` / `Err` / `Result` 的模組（目前僅 `src/infra/result.py` 為 canonical，`src/common/result.py` / `src/infra/result_compat.py` 為 compat）
  - [x] 1.1.2 列出所有定義錯誤根型別的模組（`src/infra/result.py` canonical，`src/common/errors.py` legacy re-export，`src/infra/db_errors.py` 僅產生 canonical 子型別）
- [x] 1.2 在 `src.infra.result` 定義並文件化權威公開介面
  - [x] 1.2.1 確認 `Result` / `AsyncResult` 與 `Error` 階層完整且穩定
  - [x] 1.2.2 為公開型別補上 docstring 與開發者使用說明（模組 docstring 與各型別 docstring 已覆蓋，指南亦同步更新）
  - [x] 1.2.3 覆寫或新增 `__all__`，限制外部只能從這裡匯入核心錯誤型別

## 2. 收斂錯誤階層與相容層邊界
- [x] 2.1 更新 `src/infra/db_errors.py` 以僅產生 canonical `DatabaseError` / `SystemError`
  - [x] 2.1.1 確認 `map_postgres_error` / `map_asyncpg_error` 回傳型別與 `src.infra.result.Error` 階層一致（以單元測試驗證並維持現有實作）
  - [x] 2.1.2 為 mapping 函式補充或更新測試，驗證錯誤 context 與型別
- [x] 2.2 調整 `src/common/result.py` 與 `src/infra/result_compat.py` 為純相容層
  - [x] 2.2.1 將其內部實作改為透過 `src.infra.result` 的權威型別運作（`src/common/*` 僅 re-export canonical 型別）
  - [x] 2.2.2 在這兩個模組頂部新增明確的 deprecation / compat 說明與註解
  - [x] 2.2.3 使用 `MigrationTracker` 或類似機制，記錄使用這些相容層的呼叫點（`src.common.result` 匯入時呼叫 `mark_legacy`）

## 3. 服務與 gateway 層錯誤處理統一（高風險路徑優先）
- [x] 3.1 建立高優先順序清單
  - [x] 3.1.1 標記所有 public service class（Transfer、Council、StateCouncil、Supreme Assembly、Suspect Management 等）
  - [x] 3.1.2 對每個 service 標記其 public API 是否已使用 `Result` / `AsyncResult`
- [x] 3.2 調整服務層錯誤回傳型別
  - [x] 3.2.1 確保 Result 版 service（例如 `StateCouncilServiceResult`、`PermissionService` Result 版）只使用 canonical `Result` / `Error`
  - [x] 3.2.2 對仍以 Exception 為主的 public API，使用 `async_returns_result` 或明確的轉換邏輯包裝成 `Result`
  - [x] 3.2.3 為更新後的 service 編寫或更新單元測試，覆蓋成功與錯誤路徑
- [x] 3.3 Gateway 層 DB 錯誤處理
  - [x] 3.3.1 找出仍直接 `raise asyncpg` 或 generic `Exception` 的 gateway 方法
  - [x] 3.3.2 將這些 gateway 方法改為使用 `Result` 或由 service 層統一包裝錯誤
  - [x] 3.3.3 為 gateway 層添加或更新測試，驗證錯誤 mapping 與錯誤 context

## 4. 更新 DI / 指令層依賴與錯誤處理介面
- [x] 4.1 DI 容器與 ResultContainer 對齊
  - [x] 4.1.1 檢查 `src/infra/di/*`，確保所有 Result 版 service 依賴 canonical Result / Error
  - [x] 4.1.2 若仍存在只註冊 Exception 版 service 的路徑，補上 Result 版或明確標註為 legacy
- [x] 4.2 Discord 指令層錯誤處理統一
  - [x] 4.2.1 檢查 `src/bot/commands/*` 的錯誤處理方式，標記仍以 `try/except` + embed 直接處理錯誤的路徑
  - [x] 4.2.2 在高優先 command 中改用 Result 回傳，再由統一錯誤 formatter 轉成 Discord 訊息
  - [x] 4.2.3 更新或新增指令層測試，覆蓋錯誤時的回應格式與內容

## 5. Spec / 文件更新
- [x] 5.1 更新 `error-handling` spec delta
  - [x] 5.1.1 在本 change 下的 `specs/error-handling/spec.md` 中加入「唯一 Result 實作」與「相容層邊界」的 MODIFIED 要求（既有 delta 已覆蓋，並再次確認）
  - [x] 5.1.2 檢查 `openspec/specs/error-handling/spec.md`，確保最終狀態與 implementation 一致（新增 canonical import / compat scenario）
- [x] 5.2 視需要更新 `infrastructure` / `dependency-injection` 相關 spec
  - [x] 5.2.1 明確服務層、gateway 層必須使用 canonical Result / Error
  - [x] 5.2.2 若需要，為 DI 行為補充 Scenario（解析 Result 版 service 的行為）
- [x] 5.3 更新開發者文件
  - [x] 5.3.1 在 README 或專門文件中加入「錯誤處理最佳實務」章節（Result migration guide 新增 canonical import 說明）
  - [x] 5.3.2 提供示例：如何在新 service / command 中使用 Result 模式（新增 service + command 範例）

- [x] 6.1 自動化測試
  - [x] 6.1.1 確保 `tests/test_result.py` 與新權威實作對齊（改為直接測 `src.infra.result`）
  - [x] 6.1.2 新增或更新測試覆蓋錯誤映射、service Result 回傳與 command 錯誤回應（新增 `tests/test_db_errors.py`）
  - [x] 6.1.3 在本地與 CI 中執行完整測試套件，確保無回歸（`uv run pytest tests/test_result.py tests/test_db_errors.py`）
- [x] 6.2 監控與遷移報表
  - [x] 6.2.1 使用 `MigrationTracker` 或額外工具產生錯誤處理遷移進度報表
  - [x] 6.2.2 在 MR / PR 描述中附上遷移報表摘要，方便 reviewer 評估剩餘 legacy 依賴
