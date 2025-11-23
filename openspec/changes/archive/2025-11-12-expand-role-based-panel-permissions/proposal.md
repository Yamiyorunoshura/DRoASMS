# Change: 擴充各面板的身分組權限控制

## Why
目前系統中的各個治理面板（常任理事會、國務院、最高議會、最高人民議會）只有限定的人員能夠完整使用。為了提升治理效率和參與度，需要擴充權限系統，讓擁有相關身分組的人員能夠使用對應的面板功能，例如常任理事能夠完整使用所有常任理事會功能、國土安全部部長只能使用國土安全部相關功能但無法使用國務院中其他功能。

## What Changes
- 擴充常任理事會面板權限，允許具備常任理事身分組的人員使用完整功能
- 擴充國務院面板權限，允許各部門首長使用對應部門功能，但限制跨部門操作
- 擴充國土安全部面板權限，允許具備國土安全身分組的人員使用相關功能
- 擴充最高議會面板權限，允許具備相關身分組的人員使用議會功能
- 擴充最高人民議會面板權限，允許具備相關身分組的人民代表使用功能
- 實作基於身分組的細粒度權限檢查機制
- 更新面板UI以反映新的權限結構

## Impact
- Affected specs: council-panel, state-council-panel, homeland-security-panel, supreme-assembly-panel, supreme-peoples-assembly-panel
- Affected code: src/bot/services/council_service.py, src/bot/services/state_council_service.py, 權限檢查函數, 面板UI組件
