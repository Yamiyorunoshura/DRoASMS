## Why

目前測試案例散落於 `tests/unit/`、`tests/integration/`、`tests/contracts/`、`tests/performance/` 等目錄,但缺乏統一的分類標準與標記（pytest markers），且覆蓋率存在缺口。需要建立清晰的測試分類體系（單元、整合、契約、效能），並補足關鍵領域的測試缺失，以提高測試品質與可維護性。

## What Changes

- **測試分類標準化**：為所有測試案例新增明確的 pytest marker（`@pytest.mark.unit`、`@pytest.mark.integration`、`@pytest.mark.contract`、`@pytest.mark.performance`），使測試類型清晰可識別
- **測試組織優化**：重新審視並調整現有測試的分類，確保符合 TDD 原則（單元 → 契約 → 整合 → 效能）的漸進層次
- **測試覆蓋率提升**：補足以下缺失的測試：
  - 單元測試：`src/bot/commands/` 中的指令模組（adjust.py、balance.py、transfer.py）
  - 單元測試：`src/infra/` 中的基礎設施模組（retry.py、logging/config.py）
  - 契約測試：Council 面板與 State Council 面板的完整互動流程契約
  - 整合測試：多租戶場景（多個 guild 同時操作）
  - 效能測試：Council 提案投票流程與 State Council 部門操作的效能基準
- **測試執行配置更新**：更新 `pyproject.toml` 與 `docker/bin/test.sh`，支援透過 marker 執行特定分類的測試
- **測試文件完善**：更新 README.md 與相關文件，說明測試分類標準與執行方式

## Impact

- **Affected specs**：`test-infrastructure`（新增測試分類需求）
- **Affected code**：
  - `tests/` 下所有測試檔案（新增 pytest marker）
  - `pyproject.toml`（新增 pytest marker 定義）
  - `docker/bin/test.sh`（新增依 marker 執行測試的支援）
  - 新增測試檔案：
    - `tests/unit/test_adjust_command.py`
    - `tests/unit/test_balance_command.py`
    - `tests/unit/test_transfer_command.py`
    - `tests/unit/test_retry.py`
    - `tests/unit/test_logging_config.py`
    - `tests/integration/test_multi_guild.py`
    - `tests/performance/test_council_voting.py`
    - `tests/performance/test_state_council_operations.py`
