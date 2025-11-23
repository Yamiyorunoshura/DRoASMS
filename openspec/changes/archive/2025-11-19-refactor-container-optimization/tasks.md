## 1. 容器檔案複製優化
- [x] 1.1 分析當前 .dockerignore 排除規則的完整性
- [x] 1.2 重構 docker/Dockerfile 以實施階層化檔案複製
- [x] 1.3 優化依賴安裝階層的快取效率
- [x] 1.4 重構 docker/test.Dockerfile 以減少測試容器大小
- [x] 1.5 驗證建置後映像大小減少目標達成

## 2. 增量編譯機制實施
- [x] 2.1 擴展 scripts/compile_modules.py 支援快取機制
- [x] 2.2 實作檔案變更偵測與雜湊值計算
- [x] 2.3 整合增量編譯到 Docker 建置流程
- [x] 2.4 更新 CI 管道以支援編譯快取
- [x] 2.5 驗證增量編譯效能提升

## 3. 資料庫遷移簡化
- [x] 3.1 修改 docker/bin/entrypoint.sh 移除複雜回退邏輯
- [x] 3.2 統一使用 alembic upgrade head 作為遷移策略
- [x] 3.3 更新 .env.example 移除 ALEMBIC_UPGRADE_TARGET 設定
- [x] 3.4 更新相關文檔說明新的遷移行為
- [x] 3.5 測試不同 PostgreSQL 版本的兼容性

## 4. 整合測試與驗證
- [x] 4.1 執行完整容器建置測試
- [x] 4.2 驗證所有服務正常啟動
- [x] 4.3 執行資料庫遷移測試
- [x] 4.4 執行效能基準測試
- [x] 4.5 更新部署文檔
