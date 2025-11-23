## 1. 核心容器實作
- [x] 1.1 建立 `src/infra/di/` 目錄結構
- [x] 1.2 實作 `DependencyContainer` 核心類別（註冊、解析介面）
- [x] 1.3 實作 `Lifecycle` 枚舉（Singleton、Factory、Thread-local）
- [x] 1.4 實作 Singleton 生命週期管理
- [x] 1.5 實作 Factory 生命週期管理
- [x] 1.6 實作 Thread-local 生命週期管理
- [x] 1.7 實作型別提示解析機制（從建構子參數推斷依賴）
- [x] 1.8 實作錯誤處理（未註冊依賴、循環依賴檢測）
- [x] 1.9 撰寫容器核心功能單元測試

## 2. 應用程式整合
- [x] 2.1 在 `src/bot/main.py` 建立容器實例
- [x] 2.2 註冊核心基礎設施依賴（DB Pool、Logger）
- [x] 2.3 註冊 Gateway 依賴（EconomyTransferGateway、EconomyQueryGateway 等）
- [x] 2.4 註冊 Service 依賴（TransferService、BalanceService、CouncilService 等）
- [x] 2.5 將容器傳遞給命令註冊流程

## 3. 命令模組遷移（範例）
- [x] 3.1 遷移 `src/bot/commands/transfer.py` 使用容器解析服務
- [x] 3.2 移除 `_TRANSFER_SERVICE` 模組層級單例
- [x] 3.3 更新 `build_transfer_command` 接受容器參數
- [x] 3.4 驗證轉帳功能正常運作

## 4. 測試支援
- [x] 4.1 建立測試用容器 fixture（`tests/conftest.py`）
- [x] 4.2 實作容器替換機制（允許測試註冊 mock 依賴）
- [x] 4.3 更新 `transfer` 命令相關測試使用容器
- [x] 4.4 驗證測試可正常替換依賴

## 5. 逐步遷移其他命令
- [x] 5.1 遷移 `src/bot/commands/balance.py`
- [x] 5.2 遷移 `src/bot/commands/adjust.py`
- [x] 5.3 遷移 `src/bot/commands/council.py`
- [x] 5.4 遷移 `src/bot/commands/state_council.py`
- [x] 5.5 移除所有模組層級單例變數

## 6. 文件與清理
- [x] 6.1 更新 `README.md` 說明容器使用方式
- [x] 6.2 在 `src/infra/di/` 新增 `__init__.py` 並匯出公開 API
- [x] 6.3 新增容器使用範例文件
- [x] 6.4 執行完整測試套件驗證
- [x] 6.5 效能驗證（確保無明顯開銷）
