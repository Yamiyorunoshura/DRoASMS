# Design: Add Pylance and Mypyc Support

## Context
專案目前使用 mypy 進行型別檢查（strict mode），但缺少編輯器內的即時型別檢查支援。引入 Pylance（基於 Pyright）可以提供更好的開發體驗，同時 mypyc 可以為未來效能優化提供編譯能力。

## Goals / Non-Goals

### Goals
- 提供 VS Code 編輯器內的即時型別檢查（Pylance）
- 配置 mypyc 為未來效能優化做準備
- 修復現有的 mypy 編譯錯誤
- 確保 Pylance 配置與 mypy 設定一致

### Non-Goals
- 不在此次變更中實際使用 mypyc 編譯代碼（僅配置）
- 不改變現有的 mypy 配置（僅新增 Pylance 配置）
- 不強制要求使用 VS Code（Pylance 配置不影響其他編輯器）

## Decisions

### Decision: 使用 Pyright 配置而非 Pylance 專用配置
- **Rationale**: Pylance 基於 Pyright，使用 `pyrightconfig.json` 是標準做法，且可被其他支援 Pyright 的工具使用
- **Alternatives considered**:
  - VS Code settings.json：僅限 VS Code，不夠通用
  - 僅依賴 mypy：缺少編輯器內即時檢查

### Decision: 將 mypyc 加入 dev dependencies
- **Rationale**: mypyc 是開發時工具，用於編譯和測試，不應作為運行時依賴
- **Alternatives considered**:
  - 作為 runtime dependency：不需要，mypyc 編譯的模組是預編譯的

### Decision: 保持 mypy 配置不變
- **Rationale**: 現有 mypy strict mode 配置已經完善，只需新增 Pylance 配置與其保持一致
- **Alternatives considered**:
  - 統一使用 Pyright：mypy 已經深度整合到專案中，不應改變

## Risks / Trade-offs

### Risk: Pylance 與 mypy 檢查結果不一致
- **Mitigation**: 仔細配置 `pyrightconfig.json`，確保與 mypy 設定對齊，並在 CI 中同時執行兩者

### Risk: mypyc 配置複雜度
- **Mitigation**: 先進行基本配置，未來需要時再深入優化

### Trade-off: 新增配置檔案增加維護成本
- **Mitigation**: 配置檔案相對簡單，且能顯著提升開發體驗

## Migration Plan
1. 新增配置檔案（不影響現有代碼）
2. 修復現有編譯錯誤
3. 驗證配置正確性
4. 更新文檔（如需要）

## Open Questions
- 是否需要為 mypyc 編譯建立專門的 CI 步驟？（目前僅配置，未來再考慮）
