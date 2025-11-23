# Change: Migrate DRoASMS from mypyc/mypc to Cython compilation system

## Why
現有的 mypyc/mypc 雙後端編譯系統維護複雜，且 mypyc 對某些 Python 特性的支持有限。遷移到 Cython 可以獲得更好的性能、更強的 Python 生態系統支持，並簡化編譯架構。

## What Changes
- **移除**: mypyc 和 mypc 編譯後端支持
- **移除**: 統一編譯器的多後端抽象層
- **新增**: 專用的 Cython 編譯系統
- **新增**: 16個核心模組的 Cython 實現
- **修改**: `scripts/compile_modules.py` 為 Cython 專用編譯器
- **更新**: `pyproject.toml` 配置結構
- **重構**: 所有 dataclass 為 Cython cdef class
- **實現**: Python 介面層 + Cython 核心的異步處理模式

## Impact
- **Affected specs**:
  - `unified-compilation-config` - 完全重寫編譯配置架構
  - `governance-performance` - 更新性能基準和監控
- **Affected code**:
  - 16個經濟和治理模組需要完全重寫
  - `scripts/compile_modules.py` (864行) 需要重構
  - `pyproject.toml` 配置需要更新
  - `.github/workflows/mypc-compile.yml` CI/CD 需要修改
  - 性能測試框架需要適配

## Breaking Changes
- **BREAKING**: 移除 mypyc/mypc 編譯支持，完全依賴 Cython
- **BREAKING**: 編譯配置格式變更
- **BREAKING**: 內部 dataclass 實現變更（但保持外部 API 兼容）

## Performance Expectations
- **執行速度**: 5-10x 相對於純 Python（等同或優於現有 mypyc）
- **記憶體效率**: 等同或優於現有 mypyc 實現
- **編譯時間**: 預期減少 20-30%（移除複雜後端抽象）
- **啟動時間**: 保持 ≤ 100ms 目標

## Migration Timeline
**快速遷移策略（2-3 週）**:
- **第1週**: 編譯系統重構 + 低複雜度模組遷移（6個模組）
- **第2週**: 中等複雜度模組遷移（7個模組）+ 性能測試框架
- **第3週**: 高複雜度模組遷移（3個模組）+ 集成測試 + 生產部署

## Risk Mitigation
- **性能回歸**: 建立詳細的基線測試，準備快速回滾方案
- **編譯失敗**: 實現漸進式編譯，部分失敗不影響系統運行
- **兼容性問題**: 保持所有外部 API 不變，確保無縫遷移
- **開發效率**: 提供完整的開發工具鏈和文檔

## Success Criteria
- 所有 16個模組成功遷移到 Cython
- 100% 功能測試通過
- 性能達到或超過當前 mypyc 基線
- CI/CD 管道完全適配 Cython 編譯
- 零生產環境事故
