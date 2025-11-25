# Change: Improve Slash Command Test Coverage

## Why

當前 slash commands 的測試覆蓋率僅為 53%，其中關鍵的治理命令如 state_council.py(22%)和 council.py(45%)覆蓋率嚴重不足。這影響了代碼質量和系統可靠性，特別是在 Result<T,E>錯誤處理模式遷移後，需要確保所有錯誤路徑都有適當的測試覆蓋。

## What Changes

- 提升所有 slash commands 的單元測試覆蓋率至 90%以上
- 增加 Result<T,E>錯誤處理路徑的測試案例
- 補充權限檢查、驗證錯誤和邊界條件的測試
- 確保所有命令的集成測試覆蓋主要使用場景
- 建立測試覆蓋率監控和質量門檻
- 重用現有測試基礎設施模式（get_pool() mocking、Result<T,E>輔助函數）

## Impact

- Affected specs: economy-commands, council-governance, state-council-governance, supreme-assembly-governance, help-command
- Affected code: src/bot/commands/\*.py, tests/unit/, tests/contracts/, tests/integration/
- 測試執行時間：預計增加 15-20%但確保可靠性
- 維護成本：需要持續維護高覆蓋率標準
