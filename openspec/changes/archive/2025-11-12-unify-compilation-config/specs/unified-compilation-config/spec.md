# 統一編譯配置

## ADDED Requirements

### Requirement: 統一編譯配置結構

項目 MUST 將所有編譯相關配置整合到單一的 `pyproject.toml` 文件中，包括現有分散在 `mypc.toml` 和 `Makefile` 中的配置。系統 SHALL 提供配置遷移工具以自動化此過程。

#### Scenario: 開發者在 pyproject.toml 中查看所有編譯配置

開發者打開 `pyproject.toml` 文件，能夠看到所有編譯相關的配置都在 `[tool.unified-compiler]` 區段中，包括經濟模組和治理模組的編譯設定、編譯參數、輸出目錄等。

### Requirement: 統一編譯腳本介面

系統 MUST 提供一個統一的編譯腳本，支援所有模組類型的編譯，並提供一致的命令列介面。腳本 SHALL 支持並行編譯和詳細的進度報告。

#### Scenario: 開發者使用單一命令編譯所有模組

開發者在項目根目錄運行 `python scripts/compile_modules.py --all`，腳本自動識別經濟模組和治理模組，使用適當的後端（mypyc/mypc）進行編譯，並顯示編譯進度和結果。

### Requirement: 編譯性能監控

編譯系統 MUST 提供性能監控功能，能夠檢測性能回歸並生成詳細的性能報告。系統 SHALL 在檢測到性能下降超過閾值時發出警告。

#### Scenario: CI/CD 管道檢測編譯性能回歸

CI/CD 管道在每次代碼變更後自動運行編譯，性能監控系統收集編譯時間、記憶體使用等指標，與歷史基線比較，如果檢測到性能下降超過 5%，則發出警告並阻止合併。

## MODIFIED Requirements

### Requirement: 現有編譯腳本兼容性

現有的編譯腳本 MUST 更新以讀取統一配置，同時保持向後兼容性。系統 SHALL 在遷移期間提供配置格式警告。

#### Scenario: 過渡期間使用現有腳本

開發者在遷移過渡期間繼續使用 `python scripts/compile_governance_modules.py` 命令，腳本會優先嘗試從 `pyproject.toml` 載入統一配置，如果失敗則回退到 `mypc.toml`，並在控制台顯示遷移建議。

## REMOVED Requirements

### Requirement: 移除重複配置文件

系統 MUST 移除 `mypc.toml` 和編譯相關的 `Makefile` 目標，將所有配置整合到 `pyproject.toml`。清理過程 SHALL 確保不遺留任何配置引用。

#### Scenario: 清理舊配置文件

在配置完全遷移並驗證後，運行清理腳本移除 `mypc.toml` 文件和 `Makefile` 中的 `mypc-*` 編譯目標，確保項目中只有一個編譯配置來源。
