# Change: Refactor Container Optimization

## Why
當前的容器架構存在多個效能與維護性問題：容器會複製不必要的檔案導致映像檔過大、每次建置都完全重新編譯缺乏增量建置機制、資料庫遷移版本硬編碼且具複雜的回退邏輯導致使用時的兼容性問題。

## What Changes
- **容器檔案複製優化**：重構 Dockerfile 以只複製執行期所需的檔案，利用 .dockerignore 排除不必要檔案，實施多階段建置優化
- **增量編譯機制**：導入編譯快取機制，基於檔案雜湊值實施增量編譯，避免未變更模組的重新編譯
- **資料庫遷移簡化**：移除硬編碼的遷移版本設定，統一使用 `head` 作為遷移目標，移除環境變數中的遷移設定以簡化配置

## Impact
- Affected specs: `infrastructure`, `ci-compilation`, `database-gateway`
- Affected code: `docker/Dockerfile`, `docker/test.Dockerfile`, `docker/bin/entrypoint.sh`, `.dockerignore`, `scripts/compile_modules.py`
- Performance gains: 減少容器映像大小、提升建置速度、簡化部署配置
- Maintenance improvement: 降低配置複雜度、減少兼容性問題
