# Change: Add Pylance and Mypyc Support

## Why
引入 Pylance 和 Mypyc 可以為專案提供更強大的型別檢查和編譯能力，提升代碼品質、可擴展性和可維護性。Pylance 作為 VS Code 的 Python 語言伺服器，提供即時的型別檢查和智能提示；Mypyc 則可以將 Python 代碼編譯為 C 擴展，提升執行效能。同時，本次變更將修復現有的 mypy 編譯錯誤，確保型別檢查的完整性。

## What Changes
- **引入 Pylance 配置**：新增 `pyrightconfig.json` 配置檔案，與 mypy 設定保持一致，提供 VS Code 編輯器內的型別檢查
- **引入 Mypyc 支援**：在 `pyproject.toml` 中新增 mypyc 依賴和配置，為未來效能優化做準備
- **修復編譯錯誤**：移除 `src/infra/retry.py:31` 中未使用的 `type: ignore` 註解
- **更新開發工具規範**：在 `development-tooling` spec 中新增 Pylance 和 Mypyc 相關需求

## Impact
- **Affected specs**: `development-tooling`
- **Affected code**:
  - `pyproject.toml` - 新增 mypyc 依賴和配置
  - `pyrightconfig.json` - 新增 Pylance/Pyright 配置檔案
  - `src/infra/retry.py` - 修復未使用的 type ignore 註解
  - `.vscode/settings.json` - 新增 VS Code 設定（可選，建議）
