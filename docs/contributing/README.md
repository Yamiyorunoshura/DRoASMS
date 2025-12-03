# 貢獻指南

歡迎參與 DRoASMS 專案的開發！本指南說明如何貢獻程式碼、報告問題與參與討論。

## 貢獻流程

### 1. 報告問題
- 使用 [GitHub Issues](https://github.com/Yamiyorunoshura/DRoASMS/issues) 報告錯誤或提出功能請求
- 請提供詳細的重現步驟、預期行為與實際行為
- 包含相關的日誌、錯誤訊息與環境資訊

### 2. 提交 Pull Request
1. Fork 本專案到你的 GitHub 帳號
2. 建立功能分支：`git checkout -b feature/your-feature-name`
3. 實作功能或修復錯誤
4. 確保所有測試通過，程式碼符合規範
5. 提交 Pull Request 到主專案的 `main` 分支

### 3. 程式碼審查
- 至少需要一名核心貢獻者審核通過
- 審核者會檢查程式碼品質、測試覆蓋與設計合理性
- 根據審核意見修改程式碼，直到通過審核

### 4. 合併與部署
- 通過審核的 PR 會由維護者合併
- 合併後會觸發 CI/CD 流程自動部署
- 重大變更可能會延遲部署以進行更全面的測試

## 開發環境設置

### 前置需求
- Python 3.13
- PostgreSQL 15+
- Git
- uv（推薦）或 pip

### 設置步驟
```bash
# 1. 克隆專案
git clone https://github.com/Yamiyorunoshura/DRoASMS.git
cd DRoASMS

# 2. 安裝依賴（使用 uv）
uv sync

# 3. 配置環境變數
cp .env.example .env
# 編輯 .env 填入必要的設定值

# 4. 設置資料庫
# 使用 Docker Compose 快速啟動
docker compose up -d postgres

# 或使用本地 PostgreSQL
# 建立資料庫與使用者，並啟用 pgcrypto 擴展

# 5. 執行資料庫遷移
uv run alembic upgrade head

# 6. 安裝 pre-commit hooks
make install-pre-commit
```

### 使用測試容器（推薦）
```bash
# 建置測試容器
make test-container-build

# 執行單元測試
make test-container-unit

# 執行完整 CI 流程
make ci
```

## 程式碼規範

### 程式碼風格
- 使用 **Black** 進行程式碼格式化
- 使用 **Ruff** 進行程式碼品質檢查
- 使用 **isort** 進行匯入排序
- 遵守專案現有的命名約定與模式

### 類型提示
- 所有函數與方法都必須包含完整的類型提示
- 使用 **MyPy** 與 **Pyright** 進行雙重類型檢查
- 複雜類型使用 `typing` 模組的泛型與別名

### 文檔要求
- 公開的 API 必須包含 Google 風格的文檔字串
- 複雜的演算法或邏輯需要添加註釋說明
- 更新相關的文件反映程式碼變更

### 測試要求
- 新增功能必須包含對應的單元測試
- 重大變更需要整合測試驗證端到端功能
- 測試覆蓋率不應低於現有水準
- 使用假資料生成工具（Faker）建立測試資料

## 提交規範

### 提交訊息格式
```
<類型>: <簡短描述>

<詳細說明（可選）>

<相關問題或 PR 參考（可選）>
```

### 類型說明
- `feat`: 新功能
- `fix`: 錯誤修復
- `docs`: 文件更新
- `style`: 程式碼風格調整（不影響功能）
- `refactor`: 重構（不影響功能）
- `test`: 測試相關
- `chore`: 構建過程或輔助工具變更

### 範例
```
feat: 新增轉帳事件池重試機制

- 實作指數退避重試策略
- 新增重試次數配置選項
- 添加重試相關的監控指標

Closes #123
```

## 測試指南

### 執行測試
```bash
# 執行所有測試
make test-all

# 執行單元測試
make test-unit

# 執行整合測試
make test-integration

# 執行經濟系統相關測試
make test-economy

# 執行治理系統相關測試
make test-council
```

### 編寫測試
- 測試檔案命名：`test_<模組名稱>.py`
- 測試類別命名：`Test<類別名稱>`
- 測試方法命名：`test_<場景>_<預期結果>`
- 使用 `pytest` 裝飾器與夾具（fixture）

### 測試夾具
專案提供多個測試夾具：
- `di_container`: 依賴注入容器，可替換服務實例
- `db_pool`: 資料庫連線池，用於資料庫測試
- `faker`: 假資料生成器，支援中英文 locale
- `event_loop`: asyncio 事件循環

## 設計原則

### 最小變更原則
- 每次提交專注於單一明確的變更
- 避免混合多個不相關的修改
- 保持提交的原子性與可追溯性

### 向後相容性
- 公開 API 變更需要考慮向後相容
- 必要時提供遷移路徑與棄用警告
- 資料庫變更需要提供遷移腳本

### 性能考量
- 核心路徑的變更需要性能評估
- 新增功能不應顯著降低系統性能
- 考慮使用 Cython 編譯性能關鍵模組

## 文件貢獻

### 文件類型
- **技術文件**：API 參考、架構設計、模組說明
- **使用者文件**：安裝指南、使用說明、故障排除
- **開發者文件**：貢獻指南、測試指南、部署指南

### 文件規範
- 使用 Markdown 格式撰寫
- 包含適當的標題層級與結構
- 提供程式碼範例與輸出示例
- 保持與程式碼同步更新

## 溝通協作

### 討論管道
- **GitHub Issues**: 功能請求、錯誤報告
- **GitHub Discussions**: 設計討論、問題諮詢
- **Pull Request 評論**: 程式碼審查、技術討論

### 行為準則
- 尊重所有貢獻者，無論經驗水平
- 建設性批評，專注於程式碼而非個人
- 保持專業與友善的溝通氛圍

## 認可與致謝

所有貢獻者都會在專案的 [致謝列表](../../README.md#致謝) 中列出，並根據貢獻程度可能獲得專案的協作者權限。

## 問題與幫助

如果你在貢獻過程中遇到任何問題，可以：
1. 查閱現有文件與程式碼註釋
2. 在 GitHub Discussions 提問
3. 查看相關的 Issue 與 Pull Request
4. 聯繫核心維護者尋求協助
