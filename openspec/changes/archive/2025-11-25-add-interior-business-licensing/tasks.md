## 1. 資料庫層

- [x] 1.1 創建商業許可資料表 migration（`business_licenses` 表）
- [x] 1.2 新增商業許可相關 SQL functions（申請、審批、撤銷、查詢）

## 2. Gateway 層

- [x] 2.1 新增 `BusinessLicenseGateway` 類別
- [x] 2.2 實作許可 CRUD 操作並返回 `Result<T,E>`

## 3. Service 層

- [x] 3.1 在 `state_council_service.py` 新增商業許可相關方法
- [x] 3.2 實作權限檢查（內政部領導人、國務院領袖）

## 4. 面板 UI

- [x] 4.1 內政部頁籤新增「商業許可管理」按鈕
- [x] 4.2 實作許可申請 Modal（目標用戶、許可類型、有效期）
- [x] 4.3 實作已授權用戶查看功能（分頁列表）
- [x] 4.4 實作許可撤銷功能

## 5. 測試

- [x] 5.1 新增商業許可 SQL function 單元測試
- [x] 5.2 新增 Gateway 層單元測試
- [x] 5.3 新增 Service 層單元測試
- [x] 5.4 新增面板 Contract 測試
