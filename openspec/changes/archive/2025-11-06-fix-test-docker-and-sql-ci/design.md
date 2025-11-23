## Context
專案使用 pgTAP 框架撰寫 SQL 函數測試（`tests/db/*.sql`），這些測試檔案無法直接被 `pytest` 執行。pgTAP 測試需要使用 `pg_prove` 工具，該工具會：
1. 連接到 PostgreSQL 資料庫
2. 執行 SQL 測試檔案
3. 解析 pgTAP 測試結果（TAP 格式）
4. 輸出測試報告

目前 `pg_prove` 僅安裝在 `postgres` 容器中，但測試需要在 `test` 容器中執行。

## Goals / Non-Goals
- Goals:
  - 測試容器可以執行 SQL 函數測試
  - SQL 測試正確整合到 CI 流程
  - Docker Compose 測試服務可以成功啟動
- Non-Goals:
  - 不需要將 SQL 測試轉換為 Python 測試
  - 不需要修改現有的 SQL 測試檔案格式

## Decisions
- Decision: 在測試容器中安裝 `pg_prove` 工具
  - 理由：`pg_prove` 是執行 pgTAP 測試的標準工具，測試容器需要獨立執行能力
  - 替代方案：從 postgres 容器執行（複雜度較高，需要跨容器通信）
- Decision: 使用 `pg_prove` 執行所有 `tests/db/*.sql` 檔案
  - 理由：簡單直接，符合 pgTAP 標準用法
  - 命令格式：`pg_prove -h postgres -U bot -d economy tests/db/*.sql`
- Decision: 在 `run_db()` 中直接使用 `pg_prove`，而非透過 pytest plugin
  - 理由：減少複雜度，pgTAP 測試與 Python 測試架構不同
  - 測試腳本已經支援多種測試類型（unit, contract, integration 等），可以新增 db 類型

## Risks / Trade-offs
- Risk: `pg_prove` 可能無法正確解析 `DATABASE_URL` 格式
  → Mitigation: 手動解析 `DATABASE_URL` 並提取連接參數（host, port, user, database）
- Risk: 測試容器需要 PostgreSQL client 工具以連接到資料庫
  → Mitigation: 安裝 `postgresql-client` 套件（通常已包含在基礎映像中，或需要額外安裝）
- Trade-off: 在測試容器中安裝額外工具會增加映像檔大小
  → 影響：可接受，因為 `pg_prove` 和 PostgreSQL client 都是小型工具

## Migration Plan
1. 更新 `docker/test.Dockerfile` 安裝 `pg_prove`
2. 更新 `docker/bin/test.sh` 的 `run_db()` 函數
3. 測試 `docker compose run --rm test db` 可以成功執行
4. 驗證 CI 流程包含 SQL 測試
5. 更新文檔（如果需要）

## Open Questions
- 是否需要為 SQL 測試設定特定的資料庫連接參數？
- 是否需要測試隔離（每個測試使用獨立交易）？
