# 統一編譯配置 (unify-compilation-config)

## Why

當前 DRoASMS 項目存在編譯配置分散在多個文件中的問題：
- `pyproject.toml` 包含 mypyc 經濟模組配置
- `mypc.toml` 專門用於治理模組編譯配置
- `Makefile` 包含編譯相關目標

這導致維護複雜度高、新開發者學習成本高、配置同步困難。統一編譯配置可以顯著簡化項目結構、提高開發效率。

## What Changes

1. **配置統一**：將 `mypc.toml` 中的所有配置遷移到 `pyproject.toml` 的 `[tool.unified-compiler]` 區段
2. **腳本整合**：創建 `scripts/compile_modules.py` 作為統一的編譯入口點
3. **後端抽象**：建立編譯器後端抽象介面，支持 mypyc 和 mypc
4. **性能監控**：添加編譯性能監控和基線比較功能
5. **遷移工具**：提供自動化配置遷移和驗證工具

## Implementation Plan

### Phase 1: Configuration Migration
- 將 mypc.toml 配置遷移到 pyproject.toml
- 創建統一配置結構
- 保持向後兼容性

### Phase 2: Script Unification
- 開發統一編譯腳本
- 更新現有腳本以使用新配置
- 實現性能監控

### Phase 3: Cleanup
- 移除舊配置文件
- 更新文檔
- 完成遷移

## Success Criteria

- 所有編譯配置整合到 pyproject.toml
- 統一編譯腳本正常工作
- 編譯性能不低於現有水平
- 現有工作流程保持兼容
