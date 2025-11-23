## Context

目前專案的測試執行有兩種方式：
1. 本機執行：使用 `uv run pytest`，需要本地安裝所有依賴
2. 整合測試：需要 Docker Compose，手動設置環境變數

整合測試需要 `RUN_DISCORD_INTEGRATION_TESTS` 環境變數，並且需要 Docker/Compose 可用。這導致：
- 開發者環境不一致
- CI 測試流程無法在本地完全複現
- 新成員需要大量時間配置環境

## Goals / Non-Goals

### Goals
- 提供一致的測試執行環境，消除環境差異
- 支援在本地運行完整的 CI 測試流程
- 支援所有測試類型（unit, contract, integration, performance, db）
- 簡化新成員的測試環境設置

### Non-Goals
- 取代本機測試執行（開發者仍可使用 `uv run pytest`）
- 提供測試結果的可視化界面（僅輸出測試結果）
- 支援測試排程或自動化觸發（僅提供執行環境）

## Decisions

### Decision: 使用獨立的測試容器而非在應用容器中執行測試
- **Rationale**:
  - 測試環境與應用環境分離，避免衝突
  - 測試容器可以包含所有測試依賴（dev dependencies），而應用容器只需要運行時依賴
  - 測試容器可以更頻繁地重建，不影響應用容器的穩定性
- **Alternatives considered**:
  - 在應用容器中執行測試：會增加應用容器大小，混合運行時與開發依賴
  - 使用 GitHub Actions 或 CI 服務：無法在本地運行，無法提供一致的本地體驗

### Decision: 測試容器基於 Python 3.13，使用 uv 安裝依賴
- **Rationale**:
  - 與應用容器保持一致，使用相同的 Python 版本與依賴管理工具
  - `uv` 提供快速的依賴安裝與虛擬環境管理
  - 開發依賴（dev group）包含所有測試工具（pytest, pytest-cov, pytest-xdist 等）
- **Alternatives considered**:
  - 使用不同的 Python 版本：不一致的環境可能導致問題
  - 使用 pip：`uv` 更快且與專案一致

### Decision: 測試容器透過 Docker Compose 連接到 PostgreSQL 服務
- **Rationale**:
  - 整合測試需要資料庫，使用 Compose 的服務網路可以安全連接
  - 測試容器可以等待 PostgreSQL 健康檢查後再執行測試
  - 測試結束後自動清理，不影響資料庫狀態
- **Alternatives considered**:
  - 使用外部資料庫：需要額外配置，增加複雜度
  - 在測試容器內啟動 PostgreSQL：增加容器大小與啟動時間

### Decision: 測試執行腳本支援多種測試類型
- **Rationale**:
  - 不同測試類型有不同的需求（整合測試需要 Docker，單元測試不需要）
  - 提供靈活的執行選項，開發者可以選擇運行特定測試類型
  - 支援完整的 CI 流程（格式化、lint、型別檢查、測試）
- **Alternatives considered**:
  - 單一測試命令：不夠靈活，無法選擇特定測試類型
  - 每個測試類型一個容器：過度複雜，增加維護成本

### Decision: 測試容器使用非 root 用戶執行
- **Rationale**:
  - 安全性最佳實踐
  - 與應用容器保持一致
  - 避免權限問題
- **Alternatives considered**:
  - 使用 root 用戶：不符合安全最佳實踐

### Decision: 透過 Makefile 提供測試容器快捷命令
- **Rationale**:
  - 與現有的 Makefile 測試命令（`test-unit`, `test-contract` 等）保持一致
  - 提供統一的介面，開發者無需記憶 Docker Compose 命令
  - 簡化測試容器的使用，降低學習曲線
  - Makefile 命令命名遵循現有慣例（`test-container-*` 對應 `test-*`）
- **Alternatives considered**:
  - 僅提供 Docker Compose 命令：需要開發者記憶複雜的命令
  - 使用 shell 腳本：不如 Makefile 整合性好，無法利用現有的 help 系統

## Risks / Trade-offs

### Risk: 測試容器啟動時間較長
- **Mitigation**: 使用 Docker 層快取，依賴層可以被快取，重建時只需更新程式碼層

### Risk: 測試容器與應用容器不一致
- **Mitigation**: 兩者使用相同的基礎映像（Python 3.13）與依賴管理工具（uv），確保一致性

### Risk: 整合測試需要 Discord Token
- **Mitigation**: 測試容器支援環境變數傳遞，開發者可以透過 `.env` 或環境變數提供 Token

### Trade-off: 測試容器大小 vs 功能完整性
- **Decision**: 優先考慮功能完整性，測試容器包含所有測試依賴
- **Rationale**: 測試容器主要用於 CI 與本地測試，大小不是主要考量

## Migration Plan

1. **階段一**：建立測試容器 Dockerfile 與基本配置
2. **階段二**：在 Compose 中新增測試服務，驗證基本功能
3. **階段三**：建立測試執行腳本，支援不同測試類型
4. **階段四**：更新文件，說明如何使用測試容器
5. **階段五**：在 CI 中整合測試容器（可選）

## Open Questions

- 是否需要測試結果的持久化儲存（例如 HTML 報告）？
- 是否需要支援測試的並行執行（pytest-xdist）？
- 是否需要測試容器的健康檢查？
