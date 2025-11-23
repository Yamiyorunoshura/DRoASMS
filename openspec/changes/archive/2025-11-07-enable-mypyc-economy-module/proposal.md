# Change: Enable Mypyc Compilation for Economy Module

## Why
在經濟模塊中引入 mypyc 編譯可以：
1. **發掘潛在錯誤**：mypyc 編譯過程會進行更嚴格的型別檢查，可能發現運行時才會出現的型別相關錯誤
2. **提升性能**：將 Python 代碼編譯為 C 擴展可以顯著提升執行效率，特別是對於頻繁調用的經濟操作（轉帳、餘額查詢、調整等）
3. **驗證型別安全性**：確保經濟模塊的代碼符合 mypyc 的編譯要求，驗證型別註解的完整性和正確性

經濟模塊是系統的核心功能，包含大量計算和資料庫操作，透過 mypyc 編譯可以獲得顯著的性能提升。

## What Changes
- **啟用 mypyc 編譯**：為經濟模塊的服務層和 gateway 層啟用 mypyc 編譯
- **修復編譯錯誤**：修復 mypyc 編譯過程中發現的型別錯誤和不相容問題
- **配置編譯選項**：優化 mypyc 編譯選項以獲得最佳性能
- **更新構建流程**：整合 mypyc 編譯到構建和 CI 流程中
- **性能測試**：驗證編譯後的性能提升

**影響範圍**：
- `src/bot/services/adjustment_service.py`
- `src/bot/services/transfer_service.py`
- `src/bot/services/balance_service.py`
- `src/bot/services/transfer_event_pool.py`
- `src/bot/services/currency_config_service.py`
- `src/db/gateway/economy_adjustments.py`
- `src/db/gateway/economy_transfers.py`
- `src/db/gateway/economy_queries.py`
- `src/db/gateway/economy_pending_transfers.py`
- `src/db/gateway/economy_configuration.py`

## Impact
- **Affected specs**: `development-tooling`
- **Affected code**:
  - 經濟模塊的所有服務層和 gateway 層文件
  - `pyproject.toml` - 更新 mypyc 配置
  - 構建腳本和 CI 配置（如需要）
- **Performance**: 預期經濟操作性能提升 10-30%（取決於操作類型）
- **Compatibility**: 編譯後的模塊必須保持與現有代碼的完全兼容性
