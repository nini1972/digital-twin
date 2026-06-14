from finance.data_provider import get_companies, get_intercompany_transactions, get_compliance_issues
from finance.reports import generate_income_statement, generate_balance_sheet

def perform_intercompany_reconciliation():
    """
    Check intercompany transactions and spot ledger discrepancies.
    Returns flagged mismatches.
    """
    transactions = get_intercompany_transactions()
    mismatches = []
    reconciled = []
    
    for tx in transactions:
        if tx.get("discrepancy", False):
            mismatches.append(tx)
        else:
            reconciled.append(tx)
            
    return {
        "mismatches": mismatches,
        "reconciled_count": len(reconciled),
        "status": "Warning: Intercompany discrepancies detected." if mismatches else "Success: All intercompany accounts reconcile perfectly."
    }

def audit_compliance_issues():
    """
    Run automated audits against common accounting rules (BGAAP / IFRS / IAS 38).
    Specifically flags research capitalization and details adjusting journal entries.
    """
    issues = get_compliance_issues()
    results = []
    
    # We will also programmatically verify if the data matches the rules in our compliance issues
    companies = get_companies()
    for cid, co in companies.items():
        tb = co["trial_balance"].get("FY25_actual", {})
        # programmatically double-check Capitalized Research
        cap_res = tb.get("Capitalized Research", 0.0)
        if cap_res > 0:
            # Matches issue comp_001
            for issue in issues:
                if issue["company_id"] == cid and issue["subject"] == "Capitalization of Research Costs":
                    results.append({
                        "company_id": cid,
                        "company_name": co["name"],
                        "issue_id": issue["id"],
                        "standard_violated": issue["standard_violated"],
                        "subject": issue["subject"],
                        "current_value": cap_res,
                        "description": issue["description"],
                        "remediation": issue["audit_action"],
                        "adjusting_entry": {
                            "Debit": "Research Expense (P&L)",
                            "Credit": "Capitalized Research (Balance Sheet Assets)",
                            "Amount": cap_res
                        }
                    })
                    
    return results

def calculate_financial_ratios(company_id, period="FY25_actual"):
    """
    Compute key liquidity, solvency, and profitability ratios.
    """
    try:
        inc = generate_income_statement(company_id, period)
        bs = generate_balance_sheet(company_id, period)
    except Exception as e:
        return {"error": f"Insufficient data to compute ratios: {str(e)}"}
        
    if "error" in bs:
        return bs
        
    # Extract metrics
    assets = bs["assets"]
    liab = bs["liabilities"]
    equity = bs["equity"]
    rows = inc["rows"]
    
    cash = assets.get("Cash & Cash Equivalents", 0.0)
    ar = assets.get("Accounts Receivable", 0.0)
    inv = assets.get("Inventory", 0.0)
    current_assets = cash + ar + inv # simplified current assets
    
    ap = liab.get("Accounts Payable", 0.0)
    ic_pay = liab.get("Intercompany Payables", 0.0)
    current_liabilities = ap + ic_pay # simplified current liabilities
    
    total_assets = assets.get("Total Assets", 0.0)
    total_liabilities = liab.get("Total Liabilities", 0.0)
    total_equity = equity.get("Total Equity", 0.0)
    
    ebit = rows.get("Operating Profit (EBIT)", 0.0)
    revenue = rows.get("Total Revenue", 1.0)
    net_income = rows.get("Net Income", 0.0)
    
    # Compute ratios
    current_ratio = current_assets / current_liabilities if current_liabilities > 0 else 999.0
    quick_ratio = (current_assets - inv) / current_liabilities if current_liabilities > 0 else 999.0
    debt_to_equity = total_liabilities / total_equity if total_equity > 0 else 999.0
    net_margin = net_income / revenue if revenue > 0 else 0.0
    return_on_assets = net_income / total_assets if total_assets > 0 else 0.0
    
    # Evaluate safety thresholds
    current_ratio_status = "Healthy" if current_ratio >= 1.5 else ("Acceptable" if current_ratio >= 1.0 else "Risk (Low Liquidity)")
    leverage_status = "Healthy (Low)" if debt_to_equity < 1.0 else ("Moderate" if debt_to_equity <= 2.0 else "Risk (High Leverage)")
    profitability_status = "High" if net_margin >= 0.15 else ("Moderate" if net_margin >= 0.05 else "Low")
    
    return {
        "company_id": company_id,
        "company_name": bs["company_name"],
        "period": period,
        "metrics": {
            "Current Ratio (Liquidity)": round(current_ratio, 2),
            "Quick Ratio (Acid Test)": round(quick_ratio, 2),
            "Debt-to-Equity (Solvency)": round(debt_to_equity, 2),
            "Net Profit Margin": round(net_margin, 4),
            "Return on Assets (ROA)": round(return_on_assets, 4)
        },
        "health_checks": {
            "Liquidity Health": current_ratio_status,
            "Leverage Risk": leverage_status,
            "Profitability Tier": profitability_status
        }
    }

def run_variance_analysis(company_id="parent_nv"):
    """
    Runs actual vs budget and year-over-year variance analysis.
    Only of Parent Company Solaria NV which has budgeting and historical records in data.
    """
    co = get_companies().get(company_id)
    if not co:
        return {"error": f"Company {company_id} not found."}
        
    tb_act = co["trial_balance"].get("FY25_actual", {})
    tb_bud = co["trial_balance"].get("FY25_budget", {})
    tb_ly = co["trial_balance"].get("FY24_actual", {})
    
    # 1. Actual vs Budget FY25
    act_rev = -tb_act.get("Sales", 0.0)
    bud_rev = -tb_bud.get("Sales", 0.0)
    rev_budget_var = act_rev - bud_rev
    rev_budget_pct = rev_budget_var / bud_rev if bud_rev > 0 else 0.0
    
    act_cogs = tb_act.get("COGS", 0.0)
    bud_cogs = tb_bud.get("COGS", 0.0)
    cogs_budget_var = act_cogs - bud_cogs # positive expense variance is unfavorable
    cogs_budget_pct = cogs_budget_var / bud_cogs if bud_cogs > 0 else 0.0
    
    act_wages = tb_act.get("Wages", 0.0)
    bud_wages = tb_bud.get("Wages", 0.0)
    wages_budget_var = act_wages - bud_wages
    wages_budget_pct = wages_budget_var / bud_wages if bud_wages > 0 else 0.0
    
    # 2. Year-over-Year (FY25 Actual vs FY24 Actual)
    ly_rev = -tb_ly.get("Sales", 0.0)
    rev_yoy_var = act_rev - ly_rev
    rev_yoy_pct = rev_yoy_var / ly_rev if ly_rev > 0 else 0.0
    
    ly_cogs = tb_ly.get("COGS", 0.0)
    cogs_yoy_var = act_cogs - ly_cogs
    cogs_yoy_pct = cogs_yoy_var / ly_cogs if (ly_cogs := max(ly_cogs, 1.0)) else 0.0
    
    ly_wages = tb_ly.get("Wages", 0.0)
    wages_yoy_var = act_wages - ly_wages
    wages_yoy_pct = wages_yoy_var / ly_wages if ly_wages > 0 else 0.0
    
    # Rationale commentary
    narratives = []
    if rev_yoy_pct >= 0.10:
        narratives.append(f"Sales grew strongly by {rev_yoy_pct:.1%} YoY, indicating robust adoption of solar installations.")
    if rev_budget_pct < 0:
        narratives.append(f"Sales missed the FY25 budget by {abs(rev_budget_pct):.1%} (€{abs(rev_budget_var):,.2f}), likely due to minor supply chain delays in shipping solar inverters in Q3.")
    if wages_budget_pct > 0:
        narratives.append(f"Wages went over budget by {wages_budget_pct:.1%}, reflecting the hiring of two senior AI and data integration specialists in the parent team to support the new Agentic Twin platform.")
        
    return {
        "company_id": company_id,
        "company_name": co["name"],
        "actual_vs_budget": {
            "Sales": {"actual": act_rev, "budget": bud_rev, "variance": rev_budget_var, "variance_pct": rev_budget_pct},
            "COGS": {"actual": act_cogs, "budget": bud_cogs, "variance": cogs_budget_var, "variance_pct": cogs_budget_pct},
            "Wages": {"actual": act_wages, "budget": bud_wages, "variance": wages_budget_var, "variance_pct": wages_budget_pct}
        },
        "year_over_year": {
            "Sales": {"current": act_rev, "prior": ly_rev, "variance": rev_yoy_var, "variance_pct": rev_yoy_pct},
            "COGS": {"current": act_cogs, "prior": ly_cogs, "variance": cogs_yoy_var, "variance_pct": cogs_yoy_pct},
            "Wages": {"current": act_wages, "prior": ly_wages, "variance": wages_yoy_var, "variance_pct": wages_yoy_pct}
        },
        "audit_commentary": narratives
    }

def run_comprehensive_review(company_id="parent_nv"):
    """
    Aggregates intercompany reconciliations, compliance audits, variance results, and ratios.
    """
    return {
        "intercompany": perform_intercompany_reconciliation(),
        "compliance": audit_compliance_issues(),
        "ratios": calculate_financial_ratios(company_id),
        "variances": run_variance_analysis(company_id)
    }
