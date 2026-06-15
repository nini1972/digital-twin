---
name: compliance_audit
description: Review company records for accounting standard violations (BGAAP vs IFRS research costs) and calculate financial safety ratios.
version: 1.0.0
category: accounting-compliance
requires_tools: [review_financial_records]
---
# Compliance Auditing & Ratio Analysis Playbook

## When to Use
Use this playbook when executing compliance reviews or analyzing solvency, liquidity, and leverage risks for the group's subsidiary portfolios.

## Procedure
1. Run compliance checks across all active books to verify standard alignment.
2. Locate the capitalized intangible asset lines on Solaria NV’s balance sheet.
3. Identify if any Research expenditures have been capitalized as assets (baseline warning: Solaria NV capitalized EUR 45,000 of pure research costs).
4. Flag this capitalization as a critical violation of **IFRS IAS 38 (Intangible Assets)**, which requires research costs to be immediately expensed to the Profit & Loss statement rather than balanced on the assets sheet.
5. Calculate current liquidity and solvency ratios for the entities:
   - **Current Ratio**: Current Assets / Current Liabilities (Check for value < 1.0 liquidity risk).
   - **Debt-to-Equity**: Total Liabilities / Shareholders' Equity (Check for value > 2.5 leverage risk).
   - **Interest Coverage**: EBIT / Interest Expense (Check for value < 1.5 defaults danger).
6. Compare these ratios against Dominique's limits defined in `CFO_PREFERENCES.md`.
7. Generate an executive compliance brief containing specific remedial actions (e.g., Dr. R&D Expense EUR 45,000 / Cr. Capitalized Research Assets EUR 45,000 to resolve the IAS 38 issue).
