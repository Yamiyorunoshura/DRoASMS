## Context
DRoASMS項目使用Cython編譯11個擴展模組來提升性能，當前編譯流程與主要CI/CD工作流程分離。編譯問題可能無法在本地開發中及早發現，且編譯與測試在不同的工作流程中執行，可能導致環境不一致性。

## Goals / Non-Goals
**Goals:**
- 將Cython編譯完全集成到本地和遠程CI流程中
- 確保編譯問題在本地開發階段就能發現
- 維持與現有編譯基礎設施的完全兼容性
- 使用增量編譯優化CI執行時間
- 統一本地和遠程CI環境的一致性

**Non-Goals:**
- 修改現有編譯腳本或Cython配置
- 重新設計編譯架構或目標結構
- 添加編譯性能基線檢查
- 改變編譯失敗時的阻止策略（繼續記錄但不阻止）

## Decisions

### Decision 1: 利用現有編譯基礎設施
**What**: 使用現有的`scripts/compile_modules.py`和`pyproject.toml`配置，不重新創建編譯邏輯。

**Why**:
- 現有系統已經成熟並驗證可用
- 避免重複工作和維護負擔
- 確保與Docker測試容器的兼容性

**Alternatives considered**:
- 創建新的編譯腳本專用於CI（更複雜，維護成本高）
- 直接使用setuptools構建命令（缺乏現有的優化和錯誤處理）

### Decision 2: 增量編譯策略
**What**: 使用`--incremental`標誌執行增量編譯，只在代碼變更時重新編譯相關模組。

**Why**:
- 減少CI執行時間，提高開發效率
- 利用Cython的增量編譯機制
- 符合快速迭代開發的需求

**Alternatives considered**:
- 每次都完全重新編譯（確保一致性但增加時間成本）

### Decision 3: 非阻塞式編譯錯誤處理
**What**: 編譯失敗時記錄錯誤但不阻止後續測試繼續執行。

**Why**:
- 允許開發者在一個CI運行中看到所有問題
- 避免編譯問題完全阻礙其他代碼質量檢查
- 保持開發流程的流暢性

**Alternatives considered**:
- 立即失敗並阻止整個CI（確保質量但可能降低開發效率）

### Decision 4: Makefile集成方式
**What**: 在Makefile中添加新的`compile-check`目標，並更新現有的`ci-local`命令。

**Why**:
- 保持現有命令的向後兼容性
- 提供獨立的編譯檢查命令供手動使用
- 遵循現有Makefile的模式和約定

**Alternatives considered**:
- 直接修改現有命令而不添加新目標（降低靈活性）

## Risks / Trade-offs

### Risk: CI執行時間增加
**Mitigation**: 使用增量編譯策略，只在必要時重新編譯

### Risk: 編譯錯誤被忽略
**Mitigation**: 雖然不阻止CI，但編譯錯誤會被明確記錄和顯示

### Risk: 與現有Docker測試容器的兼容性
**Mitigation**: 完全利用現有編譯腳本，不修改編譯邏輯

### Trade-off: 錯誤嚴重性 vs 開發效率
選擇了更高的開發效率，接受編譯錯誤不會完全阻止CI的權衡

## Migration Plan

### Phase 1: 本地CI集成
1. 添加`compile-check` Makefile目標
2. 更新`make ci-local`包含編譯檢查
3. 測試本地執行流程

### Phase 2: 遠程CI集成
1. 修改`.github/workflows/ci.yml`
2. 添加編譯檢查步驟
3. 確保錯誤處理正確

### Phase 3: 驗證和優化
1. 測試完整的CI流程
2. 驗證編譯產物使用情況
3. 監控執行時間影響

## Rollback Plan
如果出現問題，可以：
1. 移除Makefile中的`compile-check`目標
2. 恢復`ci-local`命令到原始狀態
3. 移除GitHub Actions中的編譯檢查步驟
4. 所有變更都是可逆的，不影響核心功能

## Open Questions
- 是否需要在編譯失敗時添加更詳細的錯誤報告機制？
- 未來是否考慮添加編譯性能基線監控？
- 是否需要為不同的編譯錯誤類型設置不同的處理策略？
