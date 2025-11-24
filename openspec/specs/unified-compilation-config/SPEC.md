# unified-compilation-config Specification

## Purpose
統一 DRoASMS 項目的 Cython 編譯配置，提供專用的 Cython 編譯系統以獲得更好的性能和更強的 Python 生態系統支持。

## Requirements

### Requirement: 統一配置結構
項目必須（MUST）將所有編譯配置整合到 `pyproject.toml` 的 `[tool.cython-compiler]` 區段，完全移除 mypyc/mypc 支持。

#### Scenario: Cython 配置區段存在
- **WHEN** 檢查 `pyproject.toml`
- **THEN** 必須存在 `[tool.cython-compiler]` 配置區段
- **AND** 必須包含經濟模組和治理模組的 Cython 編譯配置
- **AND** 必須支持 Cython 特定的編譯參數
- **AND** 不再包含任何 mypyc 或 mypc 相關配置

#### Scenario: 舊配置完全移除
- **WHEN** 檢查項目根目錄和配置文件
- **THEN** `mypc.toml` 文件必須已完全移除
- **AND** `[tool.mypyc]` 和 `[tool.mypc]` 配置區段必須已從 `pyproject.toml` 移除
- **AND** 所有 mypyc/mypc 相關依賴必須已從 `requirements.txt` 移除

### Requirement: Cython 專用編譯腳本
項目必須（MUST）提供專用的 Cython 編譯入口點 `scripts/cython_compiler.py`，完全替換現有的統一編譯器。

#### Scenario: Cython 編譯腳本存在且可執行
- **WHEN** 執行 `python scripts/cython_compiler.py`
- **THEN** 腳本必須能夠編譯所有經濟模組和治理模組
- **AND** 必須支持 Cython 特定的編譯選項和優化
- **AND** 必須提供詳細的 Cython 編譯輸出和錯誤信息
- **AND** 不再支持 mypyc 或 mypc 編譯後端

#### Scenario: Cython 編譯腳本支持參數
- **WHEN** 執行 `python scripts/cython_compiler.py --help`
- **THEN** 必須顯示支持的 Cython 特定命令行參數
- **AND** 必須支持編譯優化級別選擇（--optimize）
- **AND** 必須支持並行編譯配置（--parallel）
- **AND** 必須支持增量編譯（--incremental）

### Requirement: Cython 編譯器專用架構
項目必須（MUST）提供專用的 Cython 編譯器架構，不再支持多後端抽象。

#### Scenario: 單一 Cython 編譯器介面
- **WHEN** 使用 Cython 編譯器
- **THEN** 必須通過專用的 Cython 介面進行編譯操作
- **AND** 必須提供 Cython 特定的錯誤處理和日誌記錄
- **AND** 必須支持 Cython 編譯配置的驗證
- **AND** 不再包含任何後端抽象層或多編譯器支持

#### Scenario: Cython 編譯優化支持
- **WHEN** 使用 Cython 編譯器
- **THEN** 必須正確配置 Cython 編譯參數
- **AND** 必須支持所有模組的 Cython 優化編譯
- **AND** 必須支持不同的優化級別（O1, O2, O3）
- **AND** 必須支持特定架構優化（--march=native）

### Requirement: 性能監控
項目必須（MUST）提供編譯性能監控功能。

#### Scenario: 編譯時間監控
- **WHEN** 執行編譯操作
- **THEN** 必須記錄每個模組的編譯時間
- **AND** 必須提供編譯時間的歷史比較
- **AND** 必須識別編譯時間異常增長

#### Scenario: 基線性能比較
- **WHEN** 編譯完成後
- **THEN** 必須與歷史基線進行性能比較
- **AND** 必須報告性能回退或改進
- **AND** 必須保存性能數據供後續分析

### Requirement: 向後兼容性
項目必須（MUST）保持與現有工作流程的向後兼容性。

#### Scenario: Makefile 集成
- **WHEN** 使用 Makefile 進行編譯
- **THEN** 現有的 Makefile 目標必須繼續工作
- **AND** 必須內部調用 Cython 編譯腳本
- **AND** 必須保持相同的命令行介面

#### Scenario: 開發者工作流程
- **WHEN** 開發者進行日常開發
- **THEN** 現有的編譯命令和腳本必須繼續可用
- **AND** 必須提供清晰的遷移指南
- **AND** 必須支持漸進式遷移

### Requirement: 文檔和指南
項目必須（MUST）提供完整的文檔和使用指南。

#### Scenario: 編譯指南存在
- **WHEN** 查看項目文檔
- **THEN** 必須存在 Cython 編譯配置的使用指南
- **AND** 必須包含配置選項的詳細說明
- **AND** 必須提供故障排除指南

#### Scenario: 遷移文檔存在
- **WHEN** 進行配置遷移
- **THEN** 必須提供從 mypyc/mypc 到 Cython 的遷移指南
- **AND** 必須包含常見問題和解決方案
- **AND** 必須提供遷移檢查清單

### Requirement: Cython 編譯性能監控
系統必須（MUST）提供專用的 Cython 編譯性能監控功能。

#### Scenario: Cython 編譯時間監控
- **WHEN** 執行 Cython 編譯操作
- **THEN** 必須記錄每個模組的 Cython 編譯時間
- **AND** 必須提供 Cython 編譯時間的歷史比較
- **AND** 必須識別 Cython 編譯時間異常增長
- **AND** 必須監控 C 代碼生成和編譯階段

#### Scenario: Cython 基線性能比較
- **WHEN** Cython 編譯完成後
- **THEN** 必須與歷史 mypyc 基線進行性能比較
- **AND** 必須報告性能回退或改進
- **AND** 必須保存 Cython 性能數據供後續分析
- **AND** 必須驗證性能目標達成情況（≥5x 純 Python）

### Requirement: Cython 編譯錯誤處理
系統必須（MUST）提供專用的 Cython 編譯錯誤處理機制。

#### Scenario: Cython 編譯錯誤恢復
- **WHEN** Cython 編譯過程失敗
- **THEN** 系統必須提供詳細的 Cython 錯誤診斷信息
- **AND** 必須包含 C 編譯器錯誤輸出
- **AND** 必須提供修復建議和常見問題解決方案
- **AND** 必須支持部分編譯失敗時的漸進式恢復

#### Scenario: Cython 類型錯誤處理
- **WHEN** Cython 類型檢查失敗
- **THEN** 必須提供清晰的類型錯誤信息
- **AND** 必須標識具體的代碼位置和問題
- **AND** 必須提供類型轉換建議
- **AND** 必須支持自動類型推斷建議

### Requirement: Cython 開發工具鏈
系統必須（MUST）提供完整的 Cython 開發工具鏈支持。

#### Scenario: Cython 開發環境設置
- **WHEN** 開發者設置開發環境
- **THEN** 必須提供自動化的 Cython 環境設置腳本
- **AND** 必須包含所有必要的 Cython 依賴
- **AND** 必須配置適當的 C 編譯器環境
- **AND** 必須提供環境驗證工具

#### Scenario: Cython 調試支持
- **WHEN** 開發者需要調試 Cython 代碼
- **THEN** 必須支持 Cython 調試符號生成
- **AND** 必須提供源碼級別的調試支持
- **AND** 必須集成 GDB 或其他調試器
- **AND** 必須提供性能分析工具集成

### Requirement: Cython 模組驗證
系統必須（MUST）提供 Cython 編譯模組的驗證機制。

#### Scenario: Cython 模組兼容性驗證
- **WHEN** Cython 模組編譯完成
- **THEN** 必須驗證與 Python 原生 API 的兼容性
- **AND** 必須檢查所有公開方法的簽名
- **AND** 必須驗證異常處理行為一致性
- **AND** 必須運行兼容性測試套件

#### Scenario: Cython 性能驗證
- **WHEN** Cython 模組編譯完成
- **THEN** 必須執行性能基準測試
- **AND** 必須與純 Python 版本比較性能
- **AND** 必須驗證記憶體使用效率
- **AND** 必須確認性能目標達成
