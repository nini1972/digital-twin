---
name: reconcile_ledgers
description: Reconcile intercompany payable and receivable balances between Solaria Group NV (Parent) and Flanders Solar BV.
version: 1.0.0
category: accounting-consolidation
requires_tools: [get_financial_statements, review_financial_records]
---
# Reconcile Intercompany Ledgers Playbook

## When to Use
Use this playbook when there are reported payable/receivable mismatches between parent and subsidiary companies, particularly Flanders Solar BV and Solaria NV.

## Procedure
1. Run Scout scan using `get_financial_statements` for the entities `parent_nv` and `flanders_bv`.
2. Extract the values under `Intercompany Receivable` on the parent balance sheet and `Intercompany Payable` on the subsidiary balance sheet.
3. Compare the balances to locate the discrepancy (baseline mismatch: parent receivable EUR 48,000 vs subsidiary payable EUR 50,000).
4. Evaluate the mismatch against the materiality thresholds in `CFO_PREFERENCES.md`:
   - EUR 2,000 mismatch is above the EUR 1,000 secondary threshold, classifying it as a **Medium Severity (Orange)** compliance exception.
5. Propose a corrective Journal Voucher (JV) to eliminate the mismatch (adjust Flanders BV's intercompany payable by Dr. Intercompany Payable EUR 2,000 / Cr. Miscellaneous Administrative Revenues EUR 2,000 to balance the ledger).
6. Verify balance sheets after reconciliation to confirm that intercompany accounts equal each other exactly (receivable = payable = EUR 48,000).
