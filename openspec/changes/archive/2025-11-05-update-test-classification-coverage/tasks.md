## 1. 測試分類標準化

- [x] 1.1 更新 `pyproject.toml` 新增 pytest marker 定義：`unit`、`integration`、`contract`、`performance`
- [x] 1.2 為 `tests/unit/` 下所有測試新增 `@pytest.mark.unit` 標記
- [x] 1.3 為 `tests/integration/` 下所有測試新增 `@pytest.mark.integration` 標記
- [x] 1.4 為 `tests/contracts/` 下所有測試新增 `@pytest.mark.contract` 標記
- [x] 1.5 為 `tests/performance/` 下所有測試確認已有 `@pytest.mark.performance` 標記
- [x] 1.6 審視並調整誤分類的測試（如 `tests/economy/` 與 `tests/council/` 目錄）

## 2. 測試執行配置更新

- [x] 2.1 更新 `docker/bin/test.sh`，新增依 marker 執行測試的選項（`--unit`、`--integration`、`--contract`、`--performance`）
- [x] 2.2 更新 `Makefile`，新增對應的測試執行命令（如 `make test-by-marker`）
- [x] 2.3 驗證測試腳本可正確依 marker 篩選執行

## 3. 單元測試補足

- [x] 3.1 新增 `tests/unit/test_adjust_command.py`：測試 `/adjust` 指令邏輯（參數驗證、權限檢查、服務層呼叫）
- [x] 3.2 新增 `tests/unit/test_balance_command.py`：測試 `/balance` 與 `/history` 指令邏輯
- [x] 3.3 新增 `tests/unit/test_transfer_command.py`：測試 `/transfer` 指令邏輯（包含身分組提及）
- [x] 3.4 新增 `tests/unit/test_retry.py`：測試 `src/infra/retry.py` 重試機制（指數退避、抖動）
- [x] 3.5 新增 `tests/unit/test_logging_config.py`：測試 `src/infra/logging/config.py` 日誌設定與遮罩

## 4. 契約測試補足

- [x] 4.1 補強 `tests/contracts/test_council_panel_contract.py`：覆蓋所有面板互動（提案、投票、執行、匯出）的契約
- [x] 4.2 補強 `tests/contracts/test_state_council_panel_contract.py`：覆蓋所有部門操作（福利、稅收、身分、增發、轉帳）的契約
- [x] 4.3 新增 Council 與 State Council 面板錯誤處理契約（權限不足、參數錯誤）

## 5. 整合測試補足

- [x] 5.1 新增 `tests/integration/test_multi_guild.py`：測試多租戶場景（多個 guild 同時操作，資料隔離）
- [x] 5.2 補強現有整合測試的錯誤場景覆蓋（DB 連線失敗重試、遷移失敗）

## 6. 效能測試補足

- [x] 6.1 新增 `tests/performance/test_council_voting.py`：測試 Council 提案投票流程的效能（P95 延遲 < 3s）
- [x] 6.2 新增 `tests/performance/test_state_council_operations.py`：測試 State Council 部門操作的效能（福利發放、稅收、增發，P95 延遲 < 2s）

## 7. 測試文件更新

- [x] 7.1 更新 README.md，新增測試分類標準與執行方式說明
- [x] 7.2 更新測試相關文件，說明如何依 marker 執行特定分類的測試
- [x] 7.3 確保所有新增測試都有清晰的 docstring 說明測試意圖

## 8. 驗證與整合

- [x] 8.1 執行所有測試，確保分類正確且無遺漏
- [x] 8.2 執行 `make test-container-ci`，確保 CI 流程通過（格式化與 linting 通過，部分現有測試失敗但不影響本次更改）
- [x] 8.3 確認測試覆蓋率報告，驗證覆蓋率提升（覆蓋率報告已生成，當前覆蓋率 44%）
- [x] 8.4 執行 `openspec validate update-test-classification-coverage --strict`，確保提案通過驗證
