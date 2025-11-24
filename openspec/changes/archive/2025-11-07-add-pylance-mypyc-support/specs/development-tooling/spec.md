## ADDED Requirements

### Requirement: Pylance 型別檢查支援
專案必須（MUST）提供 Pylance/Pyright 配置，支援 VS Code 編輯器內的即時型別檢查。

#### Scenario: Pylance 配置檔案存在
- **WHEN** 檢查專案根目錄
- **THEN** 必須存在 `pyrightconfig.json` 配置檔案
- **AND** 配置必須與 mypy strict mode 設定保持一致

#### Scenario: Pylance 提供即時型別檢查
- **WHEN** 開發者在 VS Code 中編輯 Python 檔案
- **THEN** Pylance 必須提供即時的型別錯誤提示和智能補全
- **AND** 型別檢查結果必須與 mypy 檢查結果一致

### Requirement: Mypyc 編譯支援
專案必須（MUST）配置 mypyc 支援，為未來效能優化提供編譯能力。

#### Scenario: Mypyc 依賴已安裝
- **WHEN** 檢查 `pyproject.toml` 的開發依賴
- **THEN** 必須包含 `mypyc>=1.11.0` 在 `[dependency-groups.dev]` 中

#### Scenario: Mypyc 配置存在
- **WHEN** 檢查 `pyproject.toml`
- **THEN** 必須存在 `[tool.mypyc]` 配置區塊
- **AND** 配置必須為未來編譯優化做好準備

### Requirement: 型別檢查無錯誤
專案必須（MUST）通過 mypy strict mode 檢查，無任何編譯錯誤。

#### Scenario: Mypy 檢查通過
- **WHEN** 執行 `mypy src/` 指令
- **THEN** 必須無任何型別錯誤或警告
- **AND** 所有 `type: ignore` 註解必須有效且必要
