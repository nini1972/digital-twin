---
name: group_consolidation
description: Perform multi-subsidiary currency translation, elimination entries, and calculate Consolidated Balance Sheet and Income Statement (P&L).
version: 1.0.0
category: accounting-consolidation
requires_tools: [get_financial_statements, run_group_consolidation]
---
# Group Consolidation Playbook

## When to Use
Use this playbook when compiling quarterly or annual financial reports for the entire Solaria Group, combining figures across Europe (Solaria NV, Flanders BV, France SAS) and North America (US Inc.).

## Procedure
1. Load unconsolidated financial statements for all entities (`parent_nv`, `flanders_bv`, `france_sas`, `us_inc`).
2. Run currency translation on Solaria US Inc.'s accounts from USD to EUR:
   - Translate all Balance Sheet accounts using the closing spot rate of **0.91 EUR/USD**.
   - Translate all Income Statement accounts using the average period rate of **0.93 EUR/USD**.
   - Calculate the Cumulative Translation Adjustment (CTA) as the difference between the two translations, and insert it into Shareholders' Equity to ensure balance.
3. Compute Non-Controlling Interest (NCI) for Solaria France SAS:
   - Calculate 20% of France SAS's Net Income (allocated from Consolidated Earnings).
   - Calculate 20% of France SAS's Shareholders' Equity, and record it as a dedicated NCI Balance Sheet line.
4. Construct the **Elimination Journal** for intercompany transactions:
   - Eliminate Flanders BV's intercompany payable and Parent NV's intercompany receivable.
   - Eliminate Solaria US Inc.'s intercompany fee expense and Parent NV's management fee income.
5. Aggregate all translated and adjusted ledger columns to output the final Consolidated Income Statement and Consolidated Balance Sheet.
