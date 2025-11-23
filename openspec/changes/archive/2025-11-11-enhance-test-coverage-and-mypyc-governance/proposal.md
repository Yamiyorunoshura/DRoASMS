# Change: Enhance Test Coverage to 50% and Introduce Mypyc for Governance Modules

## Why
當前測試覆蓋率為47.4%，需要提升到至少50%以確保代碼品質和穩定性。同時，治理模組（State Council、Supreme Assembly等）的複雜度和性能需求較高，引入mypyc編譯可以顯著提升執行效率並保持API兼容性。

## What Changes
- **測試覆蓋率提升**：增加關鍵模組的單元測試，特別是覆蓋率較低的模組（supreme_assembly.py: 0%, council.py: 13%, state_council.py: 23%）
- **Mypyc編譯引入**：為治理模組（council_governance, state_council_governance, supreme_assembly_governance）添加mypyc編譯支持，提升5-10倍性能
- **測試基礎設施增強**：改進現有測試基礎設施，支持更好的覆蓋率監控和回歸測試
- **性能驗證**：添加性能測試以驗證mypc編譯的性能提升效果

## Impact
- Affected specs: test-infrastructure, council-governance, state-council-governance, supreme-assembly-governance
- Affected code:
  - 關鍵治理模組：src/bot/services/state_council_service.py, src/bot/services/supreme_assembly_service.py
  - 低覆蓋率命令：src/bot/commands/council.py, src/bot/commands/state_council.py, src/bot/commands/supreme_assembly.py
  - 數據網關層：src/db/gateway/council_governance.py, src/db/gateway/state_council_governance.py
- 性能提升：治理模組預期性能提升5-10倍，特別是在複雜查詢和批量操作場景
- 開發流程：添加mypyc編譯步驟到CI/CD流程，但不影響開發環境的正常運行
