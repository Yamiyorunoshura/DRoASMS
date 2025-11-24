## MODIFIED Requirements

### Requirement: Compose 測試服務
系統 SHALL 在 `compose.yaml` 中提供 `test` 服務，使用測試容器映像檔，能夠連接到 PostgreSQL 服務進行資料庫測試。測試服務 SHALL 預設啟用整合測試執行，確保所有整合測試所需的環境變數都已配置。測試專用的環境變數（如 `RUN_DISCORD_INTEGRATION_TESTS`）SHALL 在 `compose.yaml` 中設定，而非在 `.env` 檔案中，以保持生產環境配置檔案的乾淨。測試服務 SHALL 提供 Docker CLI 存取（透過掛載 Docker socket 或 Docker-in-Docker），使整合測試能夠執行 `docker compose` 命令。測試服務 SHALL 配置所有整合測試所需的環境變數（包括 `RUN_DOCKER_TESTS` 和 `TEST_MIGRATION_DB_URL`），確保測試不會因為缺少配置而被跳過。

#### Scenario: 測試服務成功啟動
- **WHEN** 開發者執行 `docker compose up test`
- **THEN** 測試服務等待 PostgreSQL 服務健康檢查通過後啟動
- **AND** 測試服務可以連接到 PostgreSQL 服務
- **AND** 測試服務使用專案根目錄作為工作目錄
- **AND** 測試服務可以存取 Docker socket，能夠執行 `docker compose` 命令

#### Scenario: 測試服務環境變數支援
- **WHEN** 開發者透過主機環境變數傳遞 `TEST_DISCORD_TOKEN` 或 `DISCORD_TOKEN`（例如：`docker compose run -e TEST_DISCORD_TOKEN=... test integration`）
- **THEN** 測試服務可以讀取這些環境變數
- **AND** 整合測試可以使用這些環境變數執行
- **AND** 測試專用的環境變數不會污染 `.env` 檔案（`.env` 僅用於生產環境配置）

#### Scenario: 整合測試預設啟用
- **WHEN** 開發者執行 `docker compose run test integration`
- **THEN** 測試服務環境變數 `RUN_DISCORD_INTEGRATION_TESTS` 在 `compose.yaml` 中預設設為 `1`（不在 `.env` 中設定）
- **AND** 所有標記為 `@pytest.mark.integration` 的測試不會因為缺少 `RUN_DISCORD_INTEGRATION_TESTS` 而被跳過
- **AND** 開發者可以透過主機環境變數傳遞 `TEST_DISCORD_TOKEN` 或 `DISCORD_TOKEN`（例如：`docker compose run -e TEST_DISCORD_TOKEN=token test integration`）
- **AND** 如果 `TEST_DISCORD_TOKEN` 或 `DISCORD_TOKEN` 未設定，測試會明確跳過並顯示清楚的訊息，而非因為缺少 `RUN_DISCORD_INTEGRATION_TESTS` 而跳過

#### Scenario: 整合測試環境變數完整性
- **WHEN** 開發者在 Docker 測試容器中執行整合測試
- **THEN** 所有整合測試所需的環境變數都已配置：
  - `RUN_DISCORD_INTEGRATION_TESTS=1`（在 `compose.yaml` 測試服務環境中預設啟用，不在 `.env` 中）
  - `RUN_DOCKER_TESTS=1`（在 `compose.yaml` 測試服務環境中預設啟用，用於需要 Docker Compose 操作的測試）
  - `TEST_MIGRATION_DB_URL`（在 `compose.yaml` 測試服務環境中設定，可從主機環境變數覆寫，用於遷移失敗測試）
  - `DATABASE_URL`（從 `.env` 或預設值）
  - `TEST_DISCORD_TOKEN` 或 `DISCORD_TOKEN`（從主機環境變數傳遞，不在 `.env` 中）
- **AND** 測試不會因為缺少必要的環境變數配置而被跳過（除非明確需要外部資源如 Discord Token）
- **AND** `.env` 檔案保持乾淨，不包含測試專用的配置

#### Scenario: Docker CLI 存取可用性
- **WHEN** 整合測試需要執行 `docker compose` 命令（如 `test_compose_dependencies.py`、`test_compose_ready.py`、`test_compose_restart_update.py`、`test_db_not_ready_retry.py`、`test_external_db_override.py`）
- **THEN** 測試容器內可以執行 `docker` 和 `docker compose` 命令
- **AND** Docker socket 已掛載到測試容器（`/var/run/docker.sock`）或 Docker-in-Docker 已配置
- **AND** 測試不會因為 Docker/Compose 不可用而被跳過
- **AND** 測試可以成功啟動和管理獨立的 Docker Compose 專案（使用 `docker_compose_project` fixture）

#### Scenario: 整合測試不因配置缺失而跳過
- **WHEN** 開發者執行 `make test-integration` 且已提供必要的資源（如 Discord token）
- **THEN** 所有整合測試都不會因為缺少 Docker/Compose 存取或缺少環境變數而被跳過
- **AND** 只有明確需要外部資源（如 Discord token）的測試才會在缺少資源時跳過
- **AND** 測試輸出清楚顯示跳過原因（例如："未提供 TEST_DISCORD_TOKEN/DISCORD_TOKEN"）
