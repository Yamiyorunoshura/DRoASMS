## Context

目前的容器架構面臨三個主要挑戰：映像大小過大由於複製了不必要的檔案、建置時間緩慢因為缺乏增量編譯機制、資料庫遷移配置複雜導致使用者兼容性問題。這些問題影響了開發效率、部署速度和維護簡易性。

專案包含 131 個 Python 檔案，總程式碼量超過 200 萬行，每次完全重新編譯耗時過長。現有的遷移機制包含複雜的回退邏輯，增加了配置複雜度和錯誤可能性。

## Goals / Non-Goals

**Goals:**
- 減少容器映像大小至少 30%
- 提升建置速度 50% 以上（增量編譯）
- 簡化遷移配置，移除環境變數依賴
- 提高開發和部署效率
- 保持向後相容性

**Non-Goals:**
- 改變應用程式核心功能
- 修改資料庫 schema 或遷移內容
- 變更現有的編譯工具鏈（Cython/mypyc）
- 支援非 PostgreSQL 資料庫

## Decisions

### 1. 多階段建置優化
**Decision**: 採用嚴格的多階段 Docker 建置，將建置依賴與運行期分離
**Rationale**: 減少最終映像大小，提升安全性和建置效率
**Implementation**:
- Build stage: 包含所有開發工具和依賴
- Runtime stage: 僅包含運行期必需檔案
- 編譯產物從 build stage 複製到 runtime stage

### 2. 檔案雜湊快取機制
**Decision**: 基於檔案內容雜湊值實施增量編譯
**Rationale**: 避免重複編譯未修改的模組，大幅提升建置速度
**Implementation**:
- 計算每個 Python 檔案的 SHA-256 雜湊
- 維護編譯狀態快取檔案
- 比較雜湊值決定是否需要重新編譯

### 3. 統一 Head 遷移策略
**Decision**: 移除版本特定遷移，統一使用 alembic upgrade head
**Rationale**: 簡化配置，減少使用者錯誤，提升兼容性
**Implementation**:
- 移除 ALEMBIC_UPGRADE_TARGET 環境變數支援
- 簡化 entrypoint.sh 遷移邏輯
- 改善錯誤訊息和診斷資訊

### 4. 增強的 .dockerignore 策略
**Decision**: 優化 .dockerignore 以排除更多不必要的檔案
**Rationale**: 減少建置上下文大小，提升建置速度
**Implementation**:
- 排除開發工具配置檔案
- 排除暫存檔案和日誌
- 排除測試和文檔目錄

## Risks / Trade-offs

### Risk 1: 增量編譯快取失效
**Risk**: 快取機制可能因檔案系統問題或並發建置而失效
**Mitigation**:
- 實施快取驗證和自動修復機制
- 提供快取清理命令
- 在 CI 環境中使用專用快取目錄

### Risk 2: 遷移相容性問題
**Risk**: 某些舊環境可能依賴特定遷移版本
**Mitigation**:
- 提供遷移指南和文檔更新
- 在發布前進行廣泛測試
- 保留緊急回退機制的文檔說明

### Trade-off: 建置複雜性 vs 效能提升
增加的增量編譯邏輯會增加建置腳本的複雜性，但帶來顯著的效能提升

### Trade-off: 配置簡化 vs 靈活性降低
移除遷移版本配置簡化了使用場景，但降低了特殊情況下的靈活性

## Migration Plan

### Phase 1: 容器優化（週 1-2）
1. 更新 .dockerignore 檔案
2. 重構 docker/Dockerfile 實施多階段建置
3. 重構 docker/test.Dockerfile
4. 測試映像大小減少效果

### Phase 2: 增量編譯實施（週 2-3）
1. 擴展 scripts/compile_modules.py
2. 實作檔案雜湊和快取機制
3. 整合到 Docker 建置流程
4. 更新 CI 管道配置
5. 效能測試和優化

### Phase 3: 遷移簡化（週 3）
1. 修改 docker/bin/entrypoint.sh
2. 更新 .env.example
3. 更新相關文檔
4. 測試各種部署場景

### Phase 4: 整合驗證（週 4）
1. 完整端對端測試
2. 效能基準測試
3. 文檔更新
4. 發布準備

## Rollback Plan

如果新機制出現問題：
- 保留原始 Dockerfile 檔案備份（.original 副檔名）
- 維持舊版編譯腳本作為備用方案
- 提供環境變數恢復舊遷移邏輯的選項
- 快速回退 hotfix 指南

## Open Questions

1. **快取持久化策略**: 如何在 CI/CD 環境中有效持久化編譯快取？
2. **並發建置**: 如何處理多個並發建置的快取競爭問題？
3. **監控指標**: 需要哪些具體指標來量化優化效果？
4. **向後相容**: 是否需要提供遷移期間的臨時相容性選項？
