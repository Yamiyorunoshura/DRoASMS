## Context

目前存在兩個 council service 實作：

- `CouncilService` (473 行) - 傳統異常處理模式，使用 try/except 和 RuntimeError
- `CouncilServiceResult` (747 行) - 新的 Result<T,E>模式，使用@async_returns_result 裝飾器

根據 project.md，Result<T,E>遷移是進行中的主動遷移，需要採用漸進式遷移策略並保持向後相容性。分析顯示約 15 個檔案使用 CouncilService，6 個檔案使用 CouncilServiceResult。

## Goals / Non-Goals

**Goals:**

- 統一 council service 實作為 Result 模式以提供類型安全的錯誤處理
- 保持現有 CouncilService API 的向後相容性
- 確保所有現有呼叫端無需立即修改即可繼續工作
- 建立清晰的遷移路徑供未來採用 Result 模式

**Non-Goals:**

- 立即強制所有呼叫端遷移到 Result 模式
- 移除現有的異常類型定義
- 破壞現有的公共 API 合約

## Decisions

**Decision 1: 內部統一，外部相容**

- CouncilService 內部實作將完全基於 CouncilServiceResult
- 保留 CouncilService 的公共 API，但內部委託給 CouncilServiceResult
- 新增異常包裝層將 Result<T,E>轉換為傳統異常

**Decision 2: 錯誤類型映射策略**

- CouncilError 層次結構映射到現有異常類型
- GovernanceNotConfiguredError → GovernanceNotConfiguredError (保持)
- CouncilValidationError → ValueError (向下相容)
- CouncilPermissionDeniedError → PermissionDeniedError (保持)
- DatabaseError → RuntimeError (向下相容)

**Decision 3: 漸進式遷移支援**

- 新增棄用警告提示開發者遷移到 Result 模式
- 在 DI 容器中同時註冊兩種服務版本
- 提供遷移指南和最佳實踐文件

## Risks / Trade-offs

**Risk 1: 錯誤語義差異**

- Result 模式提供更豐富的錯誤上下文
- 異常包裝可能遺失部分錯誤資訊
- **緩解**: 在異常訊息中包含 Result 錯誤的上下文資訊

**Risk 2: 效能影響**

- 雙層抽象可能帶來輕微效能開銷
- **緩解**: 測量並監控關鍵路徑效能，必要時進行優化

**Trade-off: 複雜性 vs 相容性**

- 保持兩套實作增加維護複雜性
- 但確保平滑遷移路徑，降低風險

## Migration Plan

**Phase 1: 核心重構**

1. 重構 CouncilService 內部實作使用 CouncilServiceResult
2. 實作 Result 到異常的轉換層
3. 添加棄用警告和遷移提示

**Phase 2: 呼叫端更新**

1. 更新 council.py 命令模組優先使用 Result 模式
2. 更新 DI 容器配置支援兩種服務
3. 更新相關服務的依賴關係

**Phase 3: 測試和驗證**

1. 更新所有測試案例
2. 執行完整回歸測試
3. 驗證向後相容性

**Rollback 策略:**

- 保留原始 CouncilService 實作的備份
- 使用功能開關控制新實作啟用
- 監控錯誤率和效能指標

## Open Questions

- 是否需要為所有 Result 方法提供異常包裝版本？
- 如何處理異步方法的錯誤轉換？
- 棄用警告的時機設定（何時開始，何時移除舊 API）？
