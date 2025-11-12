#!/bin/bash
# 治理模組部署腳本
# 用於將編譯後的治理模組部署到目標環境

set -euo pipefail

# 腳本配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build/mypc"
BACKUP_DIR="$PROJECT_ROOT/backup/deploy"
CONFIG_FILE="$PROJECT_ROOT/mypc.toml"
LOG_FILE="$PROJECT_ROOT/logs/deploy-$(date +%Y%m%d-%H%M%S).log"

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日誌函數
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

# 檢查先決條件
check_prerequisites() {
    log "檢查部署先決條件..."

    # 檢查 Python 版本
    if ! command -v python3 &> /dev/null; then
        error "Python 3 未安裝"
        exit 1
    fi

    # 檢查編譯後的模組是否存在
    if [[ ! -d "$BUILD_DIR" ]]; then
        error "編譯目錄不存在: $BUILD_DIR"
        error "請先運行編譯腳本: python scripts/compile_governance_modules.py"
        exit 1
    fi

    # 檢查配置文件
    if [[ ! -f "$CONFIG_FILE" ]]; then
        error "配置文件不存在: $CONFIG_FILE"
        exit 1
    fi

    # 創建必要目錄
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$(dirname "$LOG_FILE")"

    success "先決條件檢查通過"
}

# 備份現有模組
backup_existing_modules() {
    log "備份現有模組..."

    local modules=(
        "src/db/gateway/council_governance"
        "src/db/gateway/supreme_assembly_governance"
        "src/db/gateway/state_council_governance_mypc"
    )

    for module in "${modules[@]}"; do
        local src_path="$PROJECT_ROOT/$module.py"
        if [[ -f "$src_path" ]]; then
            local backup_path="$BACKUP_DIR/$(basename "$module").py.backup-$(date +%s)"
            cp "$src_path" "$backup_path"
            log "已備份: $module.py"
        fi
    done

    success "現有模組備份完成"
}

# 驗證編譯結果
verify_compiled_modules() {
    log "驗證編譯結果..."

    local compiled_modules=(
        "council_governance"
        "supreme_assembly_governance"
        "state_council_governance_mypc"
    )

    local failed_modules=()

    for module in "${compiled_modules[@]}"; do
        local compiled_file="$BUILD_DIR/${module}.so"
        if [[ -f "$compiled_file" ]]; then
            log "✅ 編譯模組存在: $module"
        else
            warning "⚠️  編譯模組不存在: $module (將使用 Python 版本)"
            failed_modules+=("$module")
        fi
    done

    if [[ ${#failed_modules[@]} -eq 0 ]]; then
        success "所有模組編譯成功"
        return 0
    else
        warning "部分模組編譯失敗: ${failed_modules[*]}"
        return 1
    fi
}

# 運行部署前測試
run_pre_deploy_tests() {
    log "運行部署前測試..."

    # 運行兼容性測試
    info "運行兼容性測試..."
    if python -m pytest tests/performance/test_mypc_benchmarks.py::TestCouncilGovernanceMypcCompatibility -v --tb=short; then
        success "Council governance 兼容性測試通過"
    else
        error "Council governance 兼容性測試失敗"
        return 1
    fi

    # 運行基本導入測試
    info "測試模組導入..."
    if python -c "
    try:
        from src.db.gateway.council_governance import CouncilGovernanceGateway
        from src.db.gateway.supreme_assembly_governance import SupremeAssemblyGovernanceGateway
        from src.db.gateway.state_council_governance_mypc import StateCouncilGovernanceGateway
        print('✅ 所有模組導入成功')
    except ImportError as e:
        print(f'❌ 模組導入失敗: {e}')
        exit(1)
    "; then
        success "模組導入測試通過"
    else
        error "模組導入測試失敗"
        return 1
    fi

    success "部署前測試全部通過"
}

# 部署編譯後的模組
deploy_compiled_modules() {
    log "部署編譯後的模組..."

    local deployment_target="$PROJECT_ROOT/src/db/gateway"
    local compiled_modules=(
        "council_governance"
        "supreme_assembly_governance"
        "state_council_governance_mypc"
    )

    for module in "${compiled_modules[@]}"; do
        local compiled_file="$BUILD_DIR/${module}.so"
        local target_file="$deployment_target/${module}.so"

        if [[ -f "$compiled_file" ]]; then
            # 安裝編譯後的模組
            cp "$compiled_file" "$target_file"
            log "已部署: $module.so"

            # 創建 Python 包裝器（如果需要）
            local wrapper_file="$deployment_target/${module}_wrapper.py"
            cat > "$wrapper_file" << EOF
"""
編譯後的 $module 模組包裝器
自動生成，請勿手動修改
"""

# 嘗試導入編譯版本，失敗時回退到 Python 版本
try:
    from .$module import *
except ImportError:
    import importlib
    import sys
    import os

    # 回退到 Python 版本
    module_path = os.path.join(os.path.dirname(__file__), '$module.py')
    if os.path.exists(module_path):
        spec = importlib.util.spec_from_file_location('$module', module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules['$module'] = module
        spec.loader.exec_module(module)

        # 導入所有公開符號
        from .$module import *
    else:
        raise ImportError(f"無法導入 $module 模組")
EOF

            log "已創建包裝器: ${module}_wrapper.py"
        fi
    done

    success "編譯後模組部署完成"
}

# 更新 Python 路徑配置
update_python_path() {
    log "更新 Python 路徑配置..."

    # 更新 __init__.py 文件以支持編譯後的模組
    local gateway_init="$PROJECT_ROOT/src/db/gateway/__init__.py"
    if [[ -f "$gateway_init" ]]; then
        # 備份原始文件
        cp "$gateway_init" "$gateway_init.backup-$(date +%s)"

        # 添加編譯模組支持
        cat >> "$gateway_init" << EOF

# 編譯後的治理模組支持 (自動生成)
try:
    # 嘗試導入編譯版本
    from .council_governance import *
    from .supreme_assembly_governance import *
    from .state_council_governance_mypc import *
except ImportError:
    # 編譯版本不可用時，導入 Python 版本
    try:
        from .council_governance import *
        from .supreme_assembly_governance import *
    except ImportError:
        pass  # 模組可能不存在

    # State Council 始終嘗試 mypc 版本，然後回退
    try:
        from .state_council_governance_mypc import *
    except ImportError:
        try:
            from .state_council_governance import *
        except ImportError:
            pass
EOF

        log "已更新 Python 路徑配置"
    fi

    success "Python 路徑配置更新完成"
}

# 運行部署後驗證
run_post_deploy_verification() {
    log "運行部署後驗證..."

    # 導入測試
    if python -c "
import sys
import os
sys.path.insert(0, '$PROJECT_ROOT/src')

try:
    from db.gateway.council_governance import CouncilGovernanceGateway
    from db.gateway.supreme_assembly_governance import SupremeAssemblyGovernanceGateway
    from db.gateway.state_council_governance_mypc import StateCouncilGovernanceGateway

    # 基本功能測試
    council = CouncilGovernanceGateway()
    supreme = SupremeAssemblyGovernanceGateway()
    state_council = StateCouncilGovernanceGateway()

    print('✅ 所有模組部署成功')
    print(f'✅ Council schema: {council._schema}')
    print(f'✅ Supreme Assembly schema: {supreme._schema}')
    print(f'✅ State Council schema: {state_council._schema}')
except Exception as e:
    print(f'❌ 部署驗證失敗: {e}')
    import traceback
    traceback.print_exc()
    exit(1)
    "; then
        success "部署後驗證通過"
    else
        error "部署後驗證失敗"
        return 1
    fi

    # 運行性能基準測試（可選）
    if [[ "${INCLUDE_PERFORMANCE_TESTS:-false}" == "true" ]]; then
        info "運行性能基準測試..."
        if python -m pytest tests/performance/test_mypc_benchmarks.py::TestGovernanceModulesPerformanceBenchmark -v --tb=short; then
            success "性能基準測試通過"
        else
            warning "性能基準測試失敗（不阻止部署）"
        fi
    fi
}

# 生成部署報告
generate_deploy_report() {
    log "生成部署報告..."

    local report_file="$PROJECT_ROOT/logs/deploy-report-$(date +%Y%m%d-%H%M%S).json"

    cat > "$report_file" << EOF
{
    "deployment_timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "project_root": "$PROJECT_ROOT",
    "build_directory": "$BUILD_DIR",
    "backup_directory": "$BACKUP_DIR",
    "config_file": "$CONFIG_FILE",
    "compiled_modules": [
        "council_governance",
        "supreme_assembly_governance",
        "state_council_governance_mypc"
    ],
    "status": "success",
    "log_file": "$LOG_FILE"
}
EOF

    success "部署報告已生成: $report_file"
}

# 回滾函數
rollback() {
    log "執行回滾操作..."

    local latest_backup=$(find "$BACKUP_DIR" -name "*.backup-$(date +%s)" | sort | tail -1)

    if [[ -n "$latest_backup" ]]; then
        # 恢復備份文件
        local original_file=$(echo "$latest_backup" | sed 's/.backup-[0-9]*$//')
        cp "$latest_backup" "$original_file"
        success "已回滾: $original_file"
    else
        warning "找不到備份文件，跳過回滾"
    fi

    # 清理編譯文件
    if [[ -d "$BUILD_DIR" ]]; then
        rm -rf "$BUILD_DIR"
        log "已清理編譯目錄"
    fi

    success "回滾操作完成"
}

# 主函數
main() {
    local command="${1:-deploy}"

    case "$command" in
        "deploy")
            info "開始治理模組部署..."
            check_prerequisites
            backup_existing_modules
            verify_compiled_modules
            run_pre_deploy_tests
            deploy_compiled_modules
            update_python_path
            run_post_deploy_verification
            generate_deploy_report
            success "🚀 治理模組部署成功完成！"
            ;;
        "rollback")
            warning "開始回滾操作..."
            rollback
            success "✅ 回滾操作完成"
            ;;
        "verify")
            info "運行部署驗證..."
            run_post_deploy_verification
            ;;
        *)
            echo "用法: $0 {deploy|rollback|verify}"
            exit 1
            ;;
    esac
}

# 錯誤處理
trap 'error "腳本執行失敗，行號: $LINENO"' ERR

# 執行主函數
main "$@"
