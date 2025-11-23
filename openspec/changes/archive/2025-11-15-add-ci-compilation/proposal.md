# Change: 將Cython代碼編譯集成到CI/CD工作流程

## Why
當前CI/CD流程中Cython代碼編譯與主要測試流程分離，導致編譯問題無法在本地開發中及早發現，且可能造成測試環境與生產環境的不一致性。

## What Changes
- 在本地`make ci`和`make ci-local`工作流程中添加Cython編譯檢查步驟
- 更新GitHub Actions CI工作流程，集成編譯驗證
- 添加新的Makefile目標`compile-check`，執行增量編譯和驗證
- 確保編譯錯誤被適當記錄但不阻止後續測試繼續執行
- 保持與現有編譯腳本和Docker測試容器的完全兼容性

## Impact
- **Affected specs**: ci-compilation (新增功能規範)
- **Affected code**:
  - `Makefile` - 添加編譯檢查目標和更新ci命令
  - `.github/workflows/ci.yml` - 集成編譯檢查步驟
  - `scripts/compile_modules.py` - 利用現有編譯腳本
- **Affected systems**: CI/CD流程、本地開發工作流程、代碼質量檢查

## 技術決策
- 使用增量編譯策略（`--incremental`標誌）優化性能
- 編譯錯誤記錄但不阻止CI繼續，保持開發效率
- 同時更新本地和遠程CI環境，確保一致性
- 暫時不添加性能基線檢查，專注於基本編譯功能
