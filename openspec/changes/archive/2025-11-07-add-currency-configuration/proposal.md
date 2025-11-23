## Why
目前經濟系統中貨幣名稱和圖示是硬編碼的（例如「點」、「幣」），無法根據不同伺服器的需求進行客製化。為了提升系統的靈活性和多樣性，需要允許管理員為每個 guild 設定專屬的貨幣名稱和圖示。

## What Changes
- 新增 `/currency_config` 斜線指令，允許管理員設定貨幣名稱和圖示
- 擴展 `economy.economy_configurations` 表，新增 `currency_name` 和 `currency_icon` 欄位
- 修改所有經濟相關指令（`/transfer`、`/adjust`、`/balance`、`/history`）的訊息格式，使用配置的貨幣名稱和圖示
- 修改國務院面板中與貨幣相關的顯示，使用配置的貨幣名稱和圖示
- 新增資料庫函式或 Gateway 方法來讀取和更新貨幣配置

## Impact
- Affected specs: `economy-commands`
- Affected code:
  - `src/bot/commands/` - 新增 `/currency_config` 指令
  - `src/bot/services/` - 新增或修改服務層以處理貨幣配置
  - `src/db/gateway/` - 新增或修改 Gateway 方法以讀寫貨幣配置
  - `src/db/migrations/` - 新增遷移以擴展 `economy_configurations` 表
  - `src/bot/commands/balance.py` - 修改訊息格式
  - `src/bot/commands/transfer.py` - 修改訊息格式
  - `src/bot/commands/adjust.py` - 修改訊息格式
  - `src/bot/commands/state_council.py` - 修改面板顯示
  - `src/bot/services/state_council_reports.py` - 修改報告中的貨幣顯示
