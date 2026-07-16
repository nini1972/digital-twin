# Tier 1 Memory: CFO Policies & Materiality Preferences

This document defines the statutory accounting guidelines, risk materiality thresholds, and ratio safety benchmarks used by Dominique's Digital Twin for auditing and automated reviews.

## ⚖️ Materiality Thresholds

For ledger reconciliation and auditing of the Solaria Group:
- **Primary Materiality Limit**: **EUR 5,000**
  - Any transaction discrepancy or ledger imbalance above this limit triggers an immediate **High Severity (Red)** exception warning.
- **Secondary Materiality Limit**: **EUR 1,000**
  - Discrepancies between EUR 1,000 and EUR 5,000 are recorded as **Medium Severity (Orange)** warnings that require management attention.
- **De Minimis Limit**: **EUR 100**
  - Differences below EUR 100 are considered minor rounding errors and are adjusted automatically through consolidation rounding.

---

## 📜 Statutory Accounting Rules & Policy Preferences

1. **Capitalized Research Costs (IFRS IAS 38 Audit Anomaly)**:
   - **BGAAP Rule**: Under local Belgian GAAP, certain research expenditures can be capitalized under intangible assets with strict amortisation.
   - **IFRS Rule (IAS 38)**: Under International Financial Reporting Standards, **pure research expenditures must be expensed immediately** in the Profit & Loss statement. Only Development costs meeting the six capitalization criteria can be recorded on the balance sheet.
   - **Preference**: Dominique prefers strict, high-governance IFRS alignment. Solaria NV’s **capitalized EUR 45,000 in Research Costs** must be flagged on sight as a BGAAP-to-IFRS non-compliance risk, with a directive to write an adjusting JV to immediately expense it to R&D in the Income Statement.

2. **Intercompany Profit Margins**:
   - Any intercompany profit on inventories transferred between subsidiaries must be fully eliminated in consolidation until the inventory is sold to a third party outside the Solaria Group.

---

## 📈 Financial Health Ratio Benchmarks

To audit the solvency, liquidity, and operational efficiency of the entities, the following threshold bounds are enforced:

| Financial Ratio | Formula | Healthy Range | Danger Boundary | Severity Trigger |
| :--- | :--- | :--- | :--- | :--- |
| **Current Ratio** | Current Assets / Current Liabilities | **>= 1.5** | **< 1.0** | High Liquidity Risk |
| **Debt-to-Equity** | Total Liabilities / Total Shareholders' Equity | **<= 1.5** | **> 2.5** | High Insolvency Risk |
| **Interest Coverage** | EBIT / Interest Expense | **>= 3.0** | **< 1.5** | High Default Risk |
