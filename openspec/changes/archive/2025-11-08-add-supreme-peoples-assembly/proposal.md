# Change: 新增最高人民會議系統

## Why
建立第三個治理系統「最高人民會議」，提供與理事會和國務院並行的治理功能。系統需要支援獨立的帳戶系統、表決機制（投票後不可改選）、傳召功能，並與現有經濟系統無縫整合。

## What Changes
- 新增最高人民會議系統，包含議長和議員身分組配置
- 新增最高人民會議帳戶系統（帳戶 ID：9_200_000_000_000_000 + guild_id）
- 新增表決提案機制，支援投票後不可改選
- 新增傳召功能，可傳召議員或政府官員
- 新增最高人民會議面板，支援轉帳、表決、投票、傳召等功能
- 擴展 `/adjust` 和 `/transfer` 指令支援議長身分組映射

## Impact
- Affected specs: 新增 `supreme-peoples-assembly-governance`, `supreme-peoples-assembly-panel` 兩個主要規格，並修改 `economy-commands` 規格
- Affected code: 新增 `supreme_assembly.py` 指令檔案、`SupremeAssemblyService` 服務、`SupremeAssemblyGovernanceGateway` 資料庫存取層，以及相關測試
- 與現有理事會和國務院系統並行運作，共享經濟體系但獨立帳戶
