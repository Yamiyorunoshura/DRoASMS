# Proposal: 以提及常任理事會身分組操作餘額與轉帳

- change-id: enable-council-role-mention-economy
- date: 2025-10-30
- summary:
  - /adjust 允許以「常任理事會」綁定的身分組作為目標，對理事會帳戶進行加值/扣點。
  - /transfer 允許一般用戶以提及該身分組作為受款對象，實際轉入理事會帳戶。
- affected-specs:
  - economy-commands
- rationale:
  - 目前 /adjust 與 /transfer 僅支援成員對成員。治理帳戶屬群組概念，使用身分組提及符合 Discord 使用習慣且降低輸入錯誤。
- out-of-scope:
  - 不變更餘額查詢與歷史查詢（/balance）。
  - 面板行為不在此次變更範圍。
