## Context

DRoASMS 專案目前使用手動實作處理設定驗證、重試邏輯與測試資料生成。隨著專案規模成長，這些手動實作成為維護負擔，也容易引入錯誤。

## Goals / Non-Goals

### Goals
- 使用 Pydantic 統一設定管理，提供型別安全與自動驗證
- 使用 Tenacity 簡化重試邏輯，減少重複程式碼
- 使用 Faker 自動生成測試資料，提升測試效率
- 引入 pytest-cov 監控測試覆蓋率
- 使用 pytest-xdist 加速測試執行
- 使用 pre-commit 確保提交前程式碼品質
- 為複雜邏輯引入 Hypothesis 屬性測試

### Non-Goals
- 不強制所有設定都使用 Pydantic（可漸進遷移）
- 不強制使用 CLI 工具（Typer + Rich 為選用）
- 不強制使用開發時自動重載（watchfiles 為選用）
- 不改變現有 API 或資料庫結構

## Decisions

### Decision: 使用 Pydantic v2 進行設定管理
- **Rationale**: Pydantic v2 提供優秀的型別驗證、環境變數載入與錯誤訊息，符合 Python 3.13 型別系統
- **Alternatives considered**:
  - `pydantic-settings`：已被 Pydantic v2 整合，無需額外套件
  - `python-decouple`：功能較少，缺乏型別安全
- **Implementation**: 使用 `BaseSettings`（Pydantic v2）搭配環境變數驗證

### Decision: 使用 Tenacity 處理重試邏輯
- **Rationale**: Tenacity 提供裝飾器式 API，簡化重試實作，支援多種退避策略
- **Alternatives considered**:
  - 手寫重試：當前做法，程式碼重複且難以維護
  - `backoff`：功能類似，但 Tenacity 社群更活躍
- **Implementation**: 使用 `@retry` 裝飾器搭配指數退避與抖動

### Decision: 優先導入高優先級工具
- **Rationale**: 先導入 Pydantic、pytest-cov、Faker 可立即降低開發難度
- **Implementation**: 分階段導入，先完成高優先級，再視需求加入中低優先級

### Decision: 保留 entrypoint.sh 的重試邏輯但遷移至 Python
- **Rationale**: 入口腳本需要獨立執行，但可在 Python 層面使用 Tenacity 處理重試
- **Implementation**: 在 Python 啟動前仍使用 bash 重試，但內部服務使用 Tenacity

## Risks / Trade-offs

### Risk: Pydantic 增加依賴大小
- **Mitigation**: Pydantic 為現代 Python 專案常見依賴，影響可接受

### Risk: Tenacity 可能與現有重試邏輯衝突
- **Mitigation**: 漸進遷移，先從新功能開始，再重構舊程式碼

### Risk: pytest-xdist 可能影響測試隔離
- **Mitigation**: 確保測試使用獨立資料庫連線池與交易，避免狀態共享

### Risk: pre-commit 可能增加提交時間
- **Mitigation**: 設定合理超時時間，並允許跳過（`--no-verify`）緊急情況

## Migration Plan

1. **階段一**：新增依賴與基礎設定（Pydantic、pytest-cov、Faker）
2. **階段二**：重構設定管理（`BotSettings`、`PoolConfig`）
3. **階段三**：引入 Tenacity 重構重試邏輯
4. **階段四**：設定 pytest-xdist 與 pre-commit
5. **階段五**：視需求引入 Hypothesis 與其他選用工具

### Rollback Plan
- 若 Pydantic 遷移有問題，可保留原有 `os.getenv()` 邏輯作為 fallback
- 若 Tenacity 有問題，可保留手寫重試邏輯
- 所有變更均可獨立回滾，不影響其他功能

## Open Questions

- 是否需要將所有環境變數遷移至 Pydantic？→ 先遷移核心設定，其餘漸進
- CLI 工具是否需要立即實作？→ 目前為選用，視需求再決定
- 開發時自動重載是否需要？→ 目前為選用，視開發體驗需求
