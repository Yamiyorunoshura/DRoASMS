# Cython 編譯指南

新的 Cython 編譯器取代 mypyc/mypc 雙後端，所有設定集中在 `pyproject.toml` 的 `[tool.cython-compiler]`。本指南涵蓋設定檔格式、常用指令、性能基線以及 CI 中的使用方式。

## 核心組件

- **設定檔**：`pyproject.toml` 中的 `[tool.cython-compiler]` 描述建置資料夾、併發程度、測試指令與 target 列表。
- **腳本**：`scripts/compile_modules.py` 負責編譯、清理、查詢狀態與執行測試。
- **產物**：所有 `.so` 先寫入 `build/cython/lib/<target>/`，再複製到 `src/cython_ext` 以便執行期直接匯入；純 Python fallback 仍可正常運作。

### `pyproject.toml` 片段

```toml
[tool.cython-compiler]
build_dir = "build/cython"
cache_dir = "build/cython/.cache"
parallel = "auto"
annotate = true
language_level = 3
summary_file = "build/cython/compile_report.json"
test_command = ["pytest", "-m", "performance", "-q"]

[[tool.cython-compiler.targets]]
name = "currency-config-models"
module = "src.cython_ext.currency_models"
source = "src/cython_ext/currency_models.pyx"
group = "economy"
stage = "week1"
description = "Currency configuration dataclasses"
```

## 常用指令

| 指令 | 作法 |
| --- | --- |
| 編譯全部 | `make unified-compile` 或 `python scripts/compile_modules.py compile` |
| 指定 target | `python scripts/compile_modules.py compile --module currency-config-models` |
| 清理產物 | `make unified-compile-clean` 或 `python scripts/compile_modules.py clean` |
| 狀態總覽 | `make unified-status` 或 `python scripts/compile_modules.py status` |
| 重新建立性能基線 | `python scripts/compile_modules.py compile --refresh-baseline` |
| 專用測試 | `make unified-compile-test`（呼叫 `[tool.cython-compiler].test_command`） |

## 性能基線與監控

- `scripts/performance_baseline_test.py` 會從 `pyproject` 自動載入 target 列表並量測匯入時間／記憶體，輸出到 `build/cython/baseline_pre_migration.json`。
- `compile` 指令加上 `--refresh-baseline` 時會在全部 target 成功後自動執行上述腳本。
- `build/cython/compile_report.json` 儲存每次編譯狀態，可配合 `make unified-status` 查看最近紀錄。

## CI 調整

1. Workflow 直接執行 `python scripts/compile_modules.py compile --force`，不再依賴 `mypc.toml`。
2. 編譯完成後可將 `build/cython/lib` 及報告上傳成 artifact；部署階段透過 artifact 或本地重新編譯取得 `.so`。
3. 需要性能監控時，在 CI 中追加 `--refresh-baseline` 或獨立呼叫 `scripts/performance_baseline_test.py`。

## 疑難排解

- **未安裝 Cython**：`uv pip install 'Cython>=3.0.8,<4.0.0'` 或 `uv sync`。
- **匯入 `.so` 失敗**：檢查 target `module` 路徑是否以 `src.` 開頭並與實際檔案結構一致；若懷疑快取，改用 `--force` 重新編譯。
- **仍需純 Python 版本**：刪除 `src/cython_ext/*.so` 或執行 `make unified-compile-clean` 即可回退到 fallback 模組。

## 從舊流程遷移

1. 將原本 `mypc.toml` 或 `tool.unified-compiler` 的模組清單搬到 `[tool.cython-compiler.targets]`。
2. 刪除已不用的 mypyc 專屬腳本（仍保留於 `backup/mypyc_legacy/` 供比對）。
3. 更新文件與 CI（見上方）後，執行 `make unified-compile` 確認產物與性能基線。
