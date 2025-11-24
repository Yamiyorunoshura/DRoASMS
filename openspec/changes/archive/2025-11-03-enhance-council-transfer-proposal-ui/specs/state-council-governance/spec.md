## ADDED Requirements
### Requirement: Unified Department Identification Format
系統必須（MUST）提供統一的政府部門識別格式，以 JSON 格式定義部門元資料，包含識別碼、顯示名稱、帳戶代碼等資訊。此格式必須（MUST）支援動態載入與擴展，無需在代碼中硬編碼部門列表。

#### Scenario: 部門定義載入
- GIVEN 系統啟動時存在部門定義 JSON 檔案
- WHEN 應用載入部門定義
- THEN 系統從配置載入所有部門資訊並快取於記憶體
- AND 部門定義包含以下必要欄位：id（唯一識別碼）、name（顯示名稱）、code（數值代碼）

#### Scenario: 部門查詢介面
- GIVEN 部門定義已載入
- WHEN 服務層需要查詢部門資訊
- THEN 系統提供統一的查詢介面，可依 ID、名稱或代碼查詢部門
- AND 查詢結果包含完整的部門元資料

#### Scenario: 部門列表動態取得
- GIVEN 部門定義支援動態擴展
- WHEN 需要取得所有可用部門列表
- THEN 系統從統一的部門註冊表返回當前所有部門，無需硬編碼

#### Scenario: 部門 ID 與名稱映射
- GIVEN 部門定義已載入
- WHEN 需要將部門 ID 轉換為顯示名稱，或將名稱轉換為 ID
- THEN 系統提供雙向映射功能，確保一致性

#### Scenario: 向後相容的字串名稱支援
- GIVEN 現有代碼使用字串名稱（如「內政部」）識別部門
- WHEN 使用統一的部門識別格式
- THEN 系統保留字串名稱映射，確保現有代碼仍可正常運作
- AND 允許漸進式遷移至使用部門 ID

### Requirement: Department Definition File Format
部門定義檔案必須（MUST）採用標準 JSON 格式，每個部門包含必要的識別資訊與可選的顯示屬性。

#### Scenario: JSON 格式驗證
- GIVEN 部門定義 JSON 檔案
- WHEN 系統載入檔案
- THEN 驗證 JSON 格式正確性
- AND 驗證必要欄位存在（id, name, code）
- AND 驗證 code 為有效的正整數

#### Scenario: 部門定義結構
- GIVEN 有效的部門定義 JSON
- WHEN 解析部門資訊
- THEN 每個部門物件包含：
  - `id`: 字串，唯一識別碼（如 "interior_affairs"）
  - `name`: 字串，顯示名稱（如 "內政部"）
  - `code`: 整數，帳戶 ID 推導用代碼（如 1）
  - `emoji`: 可選字串，表情符號（如 "🏘️"）

#### Scenario: 部門定義檔案缺失處理
- GIVEN 部門定義檔案不存在或無法讀取
- WHEN 系統嘗試載入部門定義
- THEN 系統記錄錯誤並使用預設部門列表作為後備
- AND 確保核心功能仍可運作
