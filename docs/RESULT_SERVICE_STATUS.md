# Result 型服務遷移狀態

本文件彙整主要服務與 gateway 的 Result 遷移現況，作為 `changes/unify-result-error-handling` 任務 3.1 的「高優先順序清單」。狀態欄位使用下列約定：

- ✅ Completed：公開 API 已回傳 `Result`/`AsyncResult`，且只依賴 `src.infra.result` 的錯誤階層。
- 🟡 Partial：部份方法已採 Result，但仍混用例外或 legacy service。
- ❌ Legacy：仍以例外為主要錯誤傳播方式，需要 compat 包裝。

## 服務層狀態

| 服務 | 模組 | 狀態 | 備註 |
| --- | --- | --- | --- |
| CouncilServiceResult | `src.bot.services.council_service_result` | ✅ Completed | 指令層已可直接透過 Result 取用，legacy `CouncilService` 僅供測試/compat。 |
| StateCouncilServiceResult | `src.bot.services.state_council_service_result` | ✅ Completed | 透過 Result 包裝大部分治理操作，並提供 `async_returns_result` gateway 包裝。 |
| PermissionService | `src.bot.services.permission_service` | 🟡 Partial → 本次更新轉為 Result API | 原檔案為例外模式；合併 `permission_service_result.py` 後改從 `src.infra.result` 匯入並回傳 `Result[PermissionResult, Error]`。 |
| SupremeAssemblyService | `src.bot.services.supreme_assembly_service` | 🟡 Partial | 已新增 `SupremeAssemblyServiceResult` 包裝並於設定指令導入 Result 流程，其餘指令持續遷移中。 |
| JusticeService | `src.bot.services.justice_service` | ❌ Legacy | 嫌犯管理仍使用例外；`StateCouncilServiceResult` 透過 compat 介面呼叫。需建立 Result 版或 gateway 包裝。 |
| TransferService | `src.bot.services.transfer_service` | 🟡 Partial | 內部 gateway 已採 Result，但對外 API 仍轉成例外以保持既有契約。未來需新增 Result 專用 facade。 |
| BalanceService / AdjustmentService | `src.bot.services.balance_service` / `adjustment_service` | ❌ Legacy | 僅在指令層少量使用，尚未導入 Result；優先度低。 |
| PermissionService (legacy) | `src.bot.services.permission_service_result` | ❌ Legacy wrapper | 保留為 re-export，相依會在 import 時列入 `MigrationTracker`。 |

## Gateway 錯誤處理現況（高風險）

| Gateway | 模組 | 狀態 | 備註 |
| --- | --- | --- | --- |
| CouncilGovernanceGateway | `src.db.gateway.council_governance` | ✅ Completed | 暫用 `@async_returns_result` 包裝 `*_result` 方法，供 Result 版服務使用。 |
| StateCouncilGovernanceGateway | `src.db.gateway.state_council_governance` | ✅ Completed | 提供 result wrapper 並在 service result 中使用。 |
| EconomyTransferGateway / AdjustmentGateway | `src.db.gateway.economy_transfers` / `economy_adjustments` | ✅ Completed | 託管層全面使用 `async_returns_result(DatabaseError, exception_map=...)`。 |
| SupremeAssemblyGovernanceGateway | `src.db.gateway.supreme_assembly_governance` | 🟡 Partial | 已提供 `*_result` 包裝與測試，後續由 service/commands 逐步改用。 |
| JusticeGovernanceGateway | `src.db.gateway.justice_governance` | ❌ Legacy | 嫌犯 CRUD 仍以例外表示；後續 Result 版 `JusticeService` 需依賴。 |
| PendingTransferGateway | `src.db.gateway.economy_pending_transfers` | 🟡 Partial | 新增 `*_result` 包裝提供 `Result` 回傳；事件池呼叫者後續需改用新介面。 |

## 待辦 / 優先排序

1. ✅（本次）建立服務狀態矩陣，作為後續開發優先級依據。
2. 🟡 針對 Supreme Assembly、Justice 服務設計 Result facade 或 wrapper。
3. 🟡 Gateway（Supreme Assembly、Justice、Pending Transfers）新增 `*_result` 方法與測試，避免例外向外逸出。
4. 🟡 更新 Discord 指令層，於高風險路徑改用 Result + 統一錯誤訊息（持續進行中）。
5. ❌ 移除對 legacy compat 模組的新引用，並以 `MigrationTracker` 報表監控殘餘使用點。

> 本文件需隨每次 Result 遷移更新，確保 Reviewer 能即時掌握尚需收斂的區域。
