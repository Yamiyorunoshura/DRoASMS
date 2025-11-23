## Context
目前經濟系統中，貨幣單位（「點」、「幣」）和相關顯示文字都是硬編碼在 Python 程式碼中。這限制了不同伺服器（guild）客製化其經濟系統的能力。為了支援多租戶環境下的客製化需求，需要將貨幣名稱和圖示配置化。

## Goals / Non-Goals
- Goals:
  - 允許每個 guild 獨立設定貨幣名稱和圖示
  - 配置變更後立即影響所有經濟相關功能
  - 保持向後相容性（未設定時使用預設值）
  - 僅限管理員（administrator 或 manage_guild 權限）可設定配置
- Non-Goals:
  - 不支援多種貨幣同時存在
  - 不支援貨幣匯率或轉換
  - 不支援貨幣圖示的自訂上傳（僅支援 emoji 或 Unicode 字元）

## Decisions
- Decision: 將貨幣配置儲存在 `economy.economy_configurations` 表中
  - Rationale: 該表已存在且用於儲存 guild 層級的經濟配置，擴展此表最符合現有架構
  - Alternatives considered: 建立新表（增加複雜度，不必要）
- Decision: 使用 emoji 或 Unicode 字元作為貨幣圖示
  - Rationale: Discord 原生支援 emoji，無需額外的圖片儲存或 CDN
  - Alternatives considered: 支援圖片 URL（需要額外的儲存和驗證邏輯）
- Decision: 預設值為「點」（名稱）和空字串（圖示）
  - Rationale: 保持與現有行為一致，確保向後相容
  - Alternatives considered: 使用「幣」作為預設（但現有程式碼多使用「點」）
- Decision: 配置變更立即生效，無需重啟
  - Rationale: 每次讀取時從資料庫載入配置，確保即時性
  - Alternatives considered: 快取配置（增加複雜度，可能導致不一致）

## Risks / Trade-offs
- Risk: 頻繁讀取資料庫可能影響效能
  → Mitigation: 可在 Service 層加入短期快取（例如 5 分鐘 TTL），但初始版本先不實作
- Risk: 惡意輸入的貨幣名稱可能破壞訊息格式
  → Mitigation: 限制貨幣名稱長度（例如最多 20 字元）並進行基本驗證
- Risk: 貨幣圖示可能包含不當內容
  → Mitigation: 限制為單一 emoji 或 Unicode 字元，並進行基本驗證

## Migration Plan
1. 新增資料庫遷移，擴展 `economy_configurations` 表
2. 為現有記錄設定預設值（currency_name='點', currency_icon=''）
3. 實作讀取和更新配置的 Gateway 方法
4. 實作 `/currency_config` 指令
5. 修改所有經濟相關指令的訊息格式
6. 測試確保向後相容性

## Open Questions
- 是否需要驗證貨幣圖示是否為有效的 emoji？
  → 初始版本僅做長度檢查，後續可加強驗證
- 是否需要在設定變更時通知所有成員？
  → 初始版本不實作，後續可考慮加入
