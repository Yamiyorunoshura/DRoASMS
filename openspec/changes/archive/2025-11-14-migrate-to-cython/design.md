# Cython Migration Technical Design

## Context
DRoASMS 項目當前使用 mypyc/mypc 雙後端編譯系統，包含 16個核心模組（10個經濟模組 + 6個治理模組）。現有系統雖然提供了性能提升，但維護複雜度高，且 mypyc 對某些 Python 特性（特別是異步操作）的支持有限。

## Constraints
- 必須保持所有外部 API 完全兼容
- 必須在 2-3 週內完成遷移
- 不能影響現有開發和生產環境
- 必須保持或改善當前性能水平
- 必須維持現有的測試覆蓋率

## Goals / Non-Goals
- **Goals**:
  - 簡化編譯架構，移除複雜的多後端抽象
  - 提升性能，特別是異步操作的性能
  - 改善開發體驗和調試能力
  - 利用 Cython 生態系統的優勢

- **Non-Goals**:
  - 重新設計業務邏輯或 API
  - 修改資料庫結構或查詢邏輯
  - 改變系統架構或模組介面
  - 添加新功能或特性

## Decisions

### Decision 1: 異步處理策略
**選擇**: Python 介面層 + Cython 核心模式

**理由**:
- Cython 對 async/await 的支持仍不如原生 Python
- 保持現有異步 API 不變
- 內部同步邏輯可以充分利用 Cython 性能優勢
- 便於調試和測試

**實現模式**:
```python
# Python 介面層（保持不變）
async def transfer_currency(self, from_id: int, to_id: int, amount: Decimal):
    return await self._transfer_impl(from_id, to_id, amount)

# Cython 核心實現
cdef class TransferService:
    cpdef async def _transfer_impl(self, int from_id, int to_id, Decimal amount):
        # Cython 優化的內部邏輯
        pass
```

### Decision 2: 數據類型轉換
**選擇**: dataclass → cdef class 轉換

**理由**:
- cdef class 提供更好的性能和記憶體效率
- 可以精確控制記憶體佈局
- 支持類型推斷和編譯時優化

**轉換模式**:
```python
# 原有 mypyc dataclass
@dataclass(frozen=True, slots=True)
@mypyc_attr(native_class=False)
class TransferEvent:
    id: int
    from_account: int
    to_account: int
    amount: Decimal
    timestamp: datetime

# 新 Cython cdef class
cdef class TransferEvent:
    cdef readonly:
        int id
        int from_account
        int to_account
        Decimal amount
        datetime timestamp

    def __init__(self, int id, int from_account, int to_account,
                 Decimal amount, datetime timestamp):
        self.id = id
        self.from_account = from_account
        self.to_account = to_account
        self.amount = amount
        self.timestamp = timestamp
```

### Decision 3: 編譯系統架構
**選擇**: 完全替換為 Cython 專用系統

**理由**:
- 移除複雜的多後端抽象，簡化維護
- Cython 提供更強大的編譯控制
- 減少編譯時間和複雜度
- 更好的錯誤診斷和調試支持

**新架構**:
```python
# scripts/cython_compiler.py
class CythonCompiler:
    def __init__(self, config):
        self.config = config

    def compile_modules(self, modules):
        # 專用 Cython 編譯邏輯
        pass

    def setup_build_environment(self):
        # Cython 特定的構建環境
        pass
```

### Decision 4: 模組遷移順序
**選擇**: 按複雜度分批遷移

**遷移順序**:
1. **低複雜度**（第1週）: 配置類型、簡單 CRUD 操作
2. **中等複雜度**（第2週）: 包含異步方法的服務層
3. **高複雜度**（第3週）: 複雜業務邏輯和事務處理

## Risks / Trade-offs

### 風險 1: 異步性能回歸
**描述**: Python 介面層可能引入性能開銷
**緩解**:
- 在介面層最小化邏輯處理
- 內部實現充分優化
- 詳細的性能基準測試

### 風險 2: 記憶體管理複雜性
**描述**: Cython 與 Python 記憶體模型差異
**緩解**:
- 使用 Python API 進行記憶體管理
- 避免手動記憶體操作
- 詳細的記憶體洩漏測試

### 風險 3: 編譯時間增加
**描述**: Cython 編譯可能比 mypyc 慢
**緩解**:
- 實現並行編譯
- 使用增量編譯
- 優化編譯參數

### 風險 4: 開發體驗下降
**描述**: Cython 語法可能影響開發效率
**緩解**:
- 提供完整的開發工具鏈
- 詳細的文檔和範例
- 保持 Python 層的可讀性

## Migration Plan

### 階段 1: 基礎設施（第1週前半）
- 設置 Cython 開發環境
- 創建新的編譯系統
- 建立性能基線測試
- 更新 CI/CD 配置

### 階段 2: 低複雜度模組（第1週後半）
**目標模組**（6個）:
- `currency_config_service.py`
- `economy_configuration.py`
- `economy_queries.py`
- `council_governance.py`
- `supreme_assembly_governance.py`
- `government_registry.py`

### 階段 3: 中等複雜度模組（第2週）
**目標模組**（7個）:
- `balance_service.py`
- `transfer_event_pool.py`
- `economy_adjustments.py`
- `economy_transfers.py`
- `economy_pending_transfers.py`
- `state_council_service.py`
- `supreme_assembly_service.py`

### 階段 4: 高複雜度模組（第3週前半）
**目標模組**（3個）:
- `transfer_service.py`
- `adjustment_service.py`
- `state_council_governance_mypc.py`

### 階段 5: 集成和部署（第3週後半）
- 端到端集成測試
- 性能驗證和優化
- 生產環境部署
- 監控和警報設置

## Implementation Patterns

### 模式 1: 類型轉換
```python
# 自動化類型轉換工具
def convert_dataclass_to_cdef(source_file, target_file):
    # 解析 dataclass 結構
    # 生成 cdef class 代碼
    # 處理類型註解轉換
    pass
```

### 模式 2: 異步包裝
```python
# 異步方法標準模式
class Service:
    async def public_method(self, *args):
        # 驗證和準備
        return await self._cython_impl(*args)

    def _cython_impl(self, *args):
        # Cython 優化的實現
        pass
```

### 模式 3: 錯誤處理
```python
# 統一的錯誤處理模式
try:
    result = await cython_operation()
except CythonError as e:
    # 轉換為標準 Python 異常
    raise PythonEquivalentError(str(e))
```

## Testing Strategy

### 單元測試
- 保持現有測試不變
- 添加 Cython 特定的性能測試
- 驗證 API 兼容性

### 集成測試
- 端到端功能測試
- 資料庫操作驗證
- 並發處理測試

### 性能測試
- 基線性能比較
- 記憶體使用分析
- 編譯時間監控

## Monitoring and Observability

### 編譯監控
- 編譯時間追蹤
- 錯誤率監控
- 成功率統計

### 運行時監控
- 性能指標收集
- 記憶體使用監控
- 異常追蹤

## Rollback Strategy

### 快速回滾
- 保持 mypyc 版本在獨立分支
- CI/CD 支持快速版本切換
- 數據庫架構保持兼容

### 漸進回滾
- 模組級別的回滾支持
- 配置驅動的版本選擇
- 運行時動態切換

## Open Questions

1. **Cython 版本選擇**: 是否使用最新的 Cython 3.0 還是穩定的 2.x 版本？
2. **編譯優化級別**: 不同模組是否需要不同的優化策略？
3. **並行編譯粒度**: 是模組級別還是文件級別的並行編譯更有效？
4. **錯誤處理策略**: Cython 編譯錯誤如何轉換為開發者友好的信息？

## Success Metrics

### 技術指標
- 編譯成功率 ≥ 99%
- 編譯時間 ≤ 當前的 120%
- 運行時性能 ≥ 當前 mypyc 水平
- 記憶體效率 ≤ 當前使用量

### 運營指標
- 零生產環境事故
- 開發者滿意度 ≥ 80%
- 問題解決時間 ≤ 2 小時
- 文檔完整性 ≥ 95%
