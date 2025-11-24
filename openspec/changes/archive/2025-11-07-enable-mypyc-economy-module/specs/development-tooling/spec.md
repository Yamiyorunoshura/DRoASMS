## MODIFIED Requirements

### Requirement: Mypyc 編譯支援
專案必須（MUST）配置 mypyc 支援，為未來效能優化提供編譯能力。專案必須（MUST）為經濟模塊啟用 mypyc 編譯，將 Python 代碼編譯為 C 擴展以提升執行效率。

#### Scenario: Mypyc 依賴已安裝
- **WHEN** 檢查 `pyproject.toml` 的開發依賴
- **THEN** 必須包含 `mypyc>=1.11.0` 在 `[dependency-groups.dev]` 中

#### Scenario: Mypyc 配置存在
- **WHEN** 檢查 `pyproject.toml`
- **THEN** 必須存在 `[tool.mypyc]` 配置區塊
- **AND** 配置必須為未來編譯優化做好準備

#### Scenario: 經濟模塊啟用 mypyc 編譯
- **WHEN** 執行構建流程
- **THEN** 經濟模塊的服務層和 gateway 層必須使用 mypyc 編譯為 C 擴展
- **AND** 編譯後的模塊必須保持與未編譯模塊的完全兼容性
- **AND** 編譯過程不得改變模塊的功能行為

#### Scenario: 編譯錯誤已修復
- **WHEN** mypyc 編譯經濟模塊時發現型別錯誤或不相容問題
- **THEN** 必須修復所有編譯錯誤
- **AND** 修復後的代碼必須通過所有現有測試
- **AND** 修復不得改變模塊的 API 或行為

#### Scenario: 編譯後的模塊功能完整
- **WHEN** 使用編譯後的經濟模塊執行操作
- **THEN** 所有功能必須與編譯前完全一致
- **AND** 所有單元測試和整合測試必須通過
- **AND** 型別檢查（mypy）必須通過

#### Scenario: 性能提升可測量
- **WHEN** 對編譯後的經濟模塊進行性能基準測試
- **THEN** 必須獲得可測量的性能提升（目標 10-30%）
- **AND** 性能測試結果必須記錄在文檔中
