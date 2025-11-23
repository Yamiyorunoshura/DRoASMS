## Context
目前專案使用單一 Dockerfile 進行建置，在所有環境中都包含相同的依賴。這導致生產環境包含了不必要的開發工具（如編譯器、測試框架、linting 工具等），增加了安全攻擊面和容器映像檔大小。開發環境則可能缺少某些便利的開發工具。

## Goals / Non-Goals
- Goals:
  - 建立環境特定的容器配置
  - 最小化生產環境映像檔大小和攻擊面
  - 提供開發環境所需的完整工具鏈
  - 保持建置流程的一致性和可維護性

- Non-Goals:
  - 改變應用程式運行邏輯
  - 修改核心依賴管理策略
  - 變更現有的啟動命令介面

## Decisions
- Decision: 採用多階段 Docker 建置，分離開發和生產環境
  - 理由：可以充分利用 Docker 層級快取，並確保生產環境只包含必要組件
- Decision: 開發環境使用完整的依賴組（包含 dev group）
  - 理由：開發時需要測試、格式化、linting 等工具
- Decision: 生產環境僅安裝運行時依賴
  - 理由：減少映像檔大小和安全風險
- Decision: 保持現有的 Makefile 介面不變
  - 理由：避免破壞現有的開發流程和腳本

- Alternatives considered:
  - 使用環境變數控制依賴安裝：會導致映像檔包含不必要的依賴
  - 建立完全分離的 Dockerfile：增加維護複雜度
  - 使用單一 Dockerfile 多個 target：技術複雜度較高

## Risks / Trade-offs
- 開發和生產環境行為可能不一致 → 確保在 CI 中測試兩種環境
- 生產環境除錯困難 → 提供專用的 debug 容器配置
- 建置時間增加 → 利用 Docker 層級快取最佳化

## Migration Plan
1. 建立新的開發專用 Dockerfile.dev
2. 修改現有 Dockerfile 為生產環境最佳化
3. 更新 compose.yaml 支援多環境建置
4. 測試 Makefile 目標確保功能正常
5. 更新文件說明新用法

## Open Questions
- 是否需要在生產環境中保留基本的除錯工具？
- 如何處理開發環境的效能最佳化（如 Cython 編譯）？
