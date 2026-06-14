import os
import sys

# Add backend directory to path to ensure imports work in tests
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from finance.reports import generate_income_statement, generate_balance_sheet, generate_cash_flow_statement
from finance.consolidation import run_consolidation
from finance.review import run_comprehensive_review, calculate_financial_ratios

def test_reports():
    """Verify that reports are generated and balance sheet balances perfectly."""
    print("Testing individual reports generation...")
    companies = ["parent_nv", "flanders_bv", "france_sas", "us_inc"]
    for cid in companies:
        inc = generate_income_statement(cid)
        bs = generate_balance_sheet(cid)
        cf = generate_cash_flow_statement(cid)
        
        print(f"  - {cid}: P&L Net Income: {inc['rows']['Net Income']:.2f}")
        
        if "error" not in bs:
            print(f"  - {cid}: BS Assets: {bs['assets']['Total Assets']:.2f} | Liab+Eq: {bs['total_liabilities_and_equity']:.2f}")
            assert bs["is_balanced"], f"Balance sheet for {cid} is not balanced! Discrepancy: {bs['discrepancy']}"
            
    print("Individual reports pass tests successfully!\n")

def test_consolidation():
    """Verify that the consolidation engine correctly aggregates and balances."""
    print("Testing consolidation engine...")
    res = run_consolidation()
    
    assert res["is_balanced"], f"Consolidated Balance Sheet is not balanced! Discrepancy: {res['discrepancy']}"
    
    bs = res["balance_sheet"]
    inc = res["income_statement"]
    
    print(f"  - Consolidated Assets: {bs['assets']['Total Assets']:.2f}")
    print(f"  - Consolidated Liab+Eq: {bs['total_liabilities_and_equity']:.2f}")
    print(f"  - Consolidated Net Income: {inc['Consolidated Net Income']:.2f}")
    print(f"  - Net Income Attributable to Parent: {inc['Net Income Attributable to Parent']:.2f}")
    print(f"  - NCI Share of Net Income: {inc['NCI Share of Net Income']:.2f}")
    
    # Verify that intercompany transactions are eliminated
    assert abs(bs["assets"]["Intercompany Receivables"]) < 0.01, "Intercompany Receivables not fully eliminated!"
    
    print("Consolidation passes tests successfully!\n")

def test_review():
    """Verify that review audits work as expected."""
    print("Testing review & audit suite...")
    res = run_comprehensive_review()
    
    # 1. Verification of compliance issue (capitalization of research)
    comp_issues = res["compliance"]
    assert len(comp_issues) > 0, "Compliance issues not flagged!"
    assert comp_issues[0]["standard_violated"] == "IFRS (IAS 38)", "IFRS violation not correctly flagged!"
    print(f"  - Compliance: Flagged {len(comp_issues)} issues. Correctly found capitalized research of {comp_issues[0]['current_value']:.2f} EUR.")
    
    # 2. Verification of intercompany mismatches
    ic_mismatches = res["intercompany"]["mismatches"]
    assert len(ic_mismatches) == 1, "Intercompany ledger mismatch was not flagged!"
    print(f"  - Intercompany Audit: Correctly flagged mismatch of Flanders receivable/payable ({ic_mismatches[0]['amount_from_perspective']} vs {ic_mismatches[0]['amount_to_perspective']}).")
    
    # 3. Ratios audit
    ratios = res["ratios"]
    print(f"  - Ratios check: Current Ratio: {ratios['metrics']['Current Ratio (Liquidity)']} | Debt-to-Equity: {ratios['metrics']['Debt-to-Equity (Solvency)']}")
    
    # 4. Variance check
    variance = res["variances"]
    print(f"  - Variances audit: Parent sales YoY growth: {variance['year_over_year']['Sales']['variance_pct']:.1%}")
    assert len(variance["audit_commentary"]) > 0, "Variance commentary was not generated!"
    
    print("Review suite passes tests successfully!\n")

if __name__ == "__main__":
    test_reports()
    test_consolidation()
    test_review()
    print("ALL TESTS PASSED SUCCESSFULLY!")
