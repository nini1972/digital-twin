# Tier 1 Memory: Solaria Group Context

This document maintains the active corporate structure, entity matrix, and accounting consolidation parameters for the Solaria Group.

## 🏢 Corporate Structure

| Entity Code | Legal Name | Jurisdiction | Functional Currency | Presentation Currency | Ownership Pct |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **parent_nv** | Solaria Group NV | Belgium | EUR | EUR | 100% (Parent) |
| **flanders_bv** | Flanders Solar BV | Belgium | EUR | EUR | 100% (Subsidiary) |
| **france_sas** | Solaria France SAS | France | EUR | EUR | 80% (Subsidiary - NCI calculated at 20%) |
| **us_inc** | Solaria US Inc. | United States | USD | EUR | 100% (Subsidiary) |

---

## 💱 Foreign Exchange Rate Matrix

For the consolidation of **Solaria US Inc. (USD)**:
- **Balance Sheet Translation (Closing Spot Rate)**: 1 USD = **0.91 EUR**
- **Income Statement Translation (Average Period Rate)**: 1 USD = **0.93 EUR**
- **Cumulative Translation Adjustment (CTA)**: Captures the balance-sheet translation difference between closing and average rates to balance Consolidated Shareholders' Equity.

---

## 🔗 Intercompany Ownership & Transactions Matrix

1. **Flanders Solar BV**:
   - Solaria Group NV holds 100% of the share capital.
   - **Intercompany Accounts Mismatch**: Solaria Group NV records a receivable of EUR 48,000 from Flanders Solar BV. Flanders Solar BV records a payable of EUR 50,000 to Solaria Group NV. This represents a **EUR 2,000 intercompany ledger mismatch** that must be reconciled by Scout.

2. **Solaria France SAS**:
   - Solaria Group NV holds 80% of the share capital. Non-controlling interest (NCI) is computed on the balance sheet and income statement at 20% of France SAS's equity and net income respectively.

3. **Solaria US Inc.**:
   - Solaria Group NV holds 100% of the share capital.
   - **Intercompany Management Fees**: Solaria Group NV charges Solaria US Inc. an annual management fee of USD 12,000 (translated at the average rate of 0.93 EUR to EUR 11,160). This is a matching transaction that must be fully eliminated (eliminated from NV fee income and US fee expense).
