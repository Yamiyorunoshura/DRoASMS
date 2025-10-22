# DRoASMS

DRoASMS 是以 Python 打造的 Discord 機器人原型，專注於社群的經濟系統與治理流程。

## 功能特色
- 經濟系統模組化管理
- 自訂治理流程與投票工具
- 互動式社群參與體驗

## 系統需求
- Python 3.12 或更新版本（完整支援 async/await）
- PostgreSQL 16 以上版本（儲存帳戶、交易與治理資料）
- 推薦使用 `uv` 或 `pip` 做為套件管理工具

## 安裝步驟
```bash
# 取得原始碼
git clone https://github.com/Yamiyorunoshura/DRoASMS.git

# 進入專案目錄
cd DRoASMS

# 建立虛擬環境（可自選管理工具）
python3 -m venv .venv
source .venv/bin/activate  # Windows 使用 .venv\Scripts\activate

# 安裝專案依賴
# 若使用 pip-tools / uv，請依照團隊鎖定檔操作
pip install -r requirements.txt  # 於依賴檔建立後執行
```

> 目前內建的 Python 腳本僅使用標準函式庫，若暫時沒有依賴檔可略過最後一步。

## 開發與執行
```bash
# 啟動虛擬環境（若尚未啟用）
source .venv/bin/activate

# 需求文檔拆分工具
python sunnycore/scripts/shard-requirements.py

# 架構文檔拆分工具
python sunnycore/scripts/shard-architecture.py

# 後續將提供 Discord Bot 入口模組與啟動指令
```

## 環境設定
在專案根目錄建立 `.env` 檔案，填入必要的 Discord 憑證與設定：

```
DISCORD_TOKEN=your_bot_token_here
```

如果需要多個環境設定，可使用 `.env.development.local`、`.env.production.local` 等檔案搭配設定管理工具。

## 測試與品質維護
```bash
# 單元測試（建立 pytest 測試後）
pytest

# 型別檢查
mypy sunnycore/

# 程式碼品質檢查
ruff check .
```

> 測試與 Lint 設定將在 Python 模組完成後一併釋出，以上指令先做為開發流程指引。

## 貢獻指南
歡迎提交 Issue 或 Pull Request，分享你的想法與改善建議。

## 授權條款
本專案採用 Apache License 2.0，詳細內容請參考 [LICENSE](LICENSE)。

## 作者群
- Yamiyorunoshura

## 致謝
- 建立於 Python + PostgreSQL 生態系
- 感謝 Discord API 提供的整合能力
