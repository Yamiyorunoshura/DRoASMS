# 統一編譯器指南

統一編譯器將原本散落於 `pyproject.toml`、`mypc.toml` 與多個腳本中的編譯設定整合為單一入口，並提供性能監控、基線比較與回歸偵測。本文檔說明如何遷移、編譯、監控以及維護統一配置。

## 遷移流程

1. `make unified-migrate-dry-run`：預覽 pyproject 將新增/更新的 `[tool.unified-compiler]` 區段。
2. `make unified-migrate`：實際寫入統一配置並在 `backup/config_migration/` 產生備份。
3. 確認 `pyproject.toml` 中的模組列表、後端設定與 `monitoring` 參數是否符合需求。
4. 刪除 `mypc.toml`（若尚未移除），並確保 CI/部署腳本不再引用舊檔。
5. 依據下節流程執行測試與編譯以驗證遷移結果。

## 編譯與測試

- `make unified-compile`：根據 `[tool.unified-compiler]` 編譯所有模組，並自動備份純 Python 版本。
- `make unified-compile-test`：只執行設定中的兼容性/性能測試，用於 CI smoke 或本地驗證。
- `make unified-compile-clean`：清理 `build/unified`、測試報告與暫存檔。
- `make unified-status`：讀取 `build/unified/compile_report.json`，顯示最新的編譯耗時與成功率。
- `make unified-refresh-baseline`：在確認結果穩定後刷新性能基線（詳見下一節）。
## 性能監控與回歸偵測

統一編譯器在 `build/unified/compile_report.json` 中輸出兩段資訊：

- `performance`：包含本次編譯耗時、成功率、峰值記憶體與編譯上下文。
- `monitoring`：紀錄是否建立/刷新基線、偵測到的回歸項目，以及絕對警示（例如峰值記憶體超標）。

基線檔路徑由 `[tool.unified-compiler.monitoring].baseline_file` 控制，預設為 `build/unified/perf_baseline.json`。當首次執行或舊檔不存在時會自動建立；若需要更新基準，請在穩定版本上執行 `make unified-refresh-baseline`。若監控偵測到超過 `regression_threshold_percent` 的退化，`scripts/compile_modules.py` 會回傳非零狀態以阻止 CI 合併。

## 舊腳本與降級策略

- 原 `scripts/compile_governance_modules.py`、`scripts/mypyc_economy_setup.py` 與 `scripts/deploy_governance_modules.sh` 已移至 `scripts/archive/`，並留下一個會提示錯誤的 stub。
- 如需比對歷史邏輯，可直接檢視該目錄的原始碼；新流程僅支援 `scripts/compile_modules.py`。
- 若需要回退，可保留 `build/unified` 生成的 `.so` 之外，仍可將 `deployment.keep_python_fallback` 設為 `true` 以確保 Python 版本存在。
