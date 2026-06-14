import json
import traceback
import sys
import os
import io

from finance.reports import generate_income_statement, generate_balance_sheet, generate_cash_flow_statement
from finance.consolidation import run_consolidation
from finance.review import run_comprehensive_review, calculate_financial_ratios
from finance.agent_framework import AgenticOrchestrator, ExecutionLog

def build_finance_tools():
    """
    Build the list of OpenAI-compatible function calling schemas.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "get_financial_statements",
                "description": "Fetch Balance Sheet, Income Statement (P&L), and Cash Flow Statement for a specific subsidiary or parent entity in the Solaria Group.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company_id": {
                            "type": "string",
                            "enum": ["parent_nv", "flanders_bv", "france_sas", "us_inc"],
                            "description": "The ID of the company to query (e.g., 'parent_nv' for Solaria Group NV, 'us_inc' for Solaria US Inc)."
                        },
                        "period": {
                            "type": "string",
                            "default": "FY25_actual",
                            "description": "The financial period (e.g., 'FY25_actual', 'FY25_budget', 'FY24_actual')."
                        }
                    },
                    "required": ["company_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_group_consolidation",
                "description": "Consolidate the entities of Solaria Group, performing foreign currency translation, aggregating accounts, doing intercompany eliminations (receivables, payables, management fees), and calculating Non-Controlling Interest (NCI).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "period": {
                            "type": "string",
                            "default": "FY25_actual",
                            "description": "The financial period to consolidate."
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "review_financial_records",
                "description": "Perform comprehensive auditing, intercompany reconciliations, rule-based compliance checks (IFRS vs. BGAAP, IAS 38), financial ratio analysis, and YoY/Budget variance review for the Solaria Group.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company_id": {
                            "type": "string",
                            "default": "parent_nv",
                            "description": "The focal company to review. Default is the parent 'parent_nv'."
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_financial_figure",
                "description": "Adjust or write a specific financial figure directly back to the trial balance database. Immediately compiles and updates the live consolidated/audited statements.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company_id": {
                            "type": "string",
                            "enum": ["parent_nv", "flanders_bv", "france_sas", "us_inc"],
                            "description": "The ID of the company to adjust."
                        },
                        "period": {
                            "type": "string",
                            "default": "FY25_actual",
                            "description": "The financial period."
                        },
                        "account": {
                            "type": "string",
                            "description": "The exact account name to modify (e.g., 'Cash', 'Sales', 'COGS', 'Wages', 'Rent Expense', etc.)."
                        },
                        "new_value": {
                            "type": "number",
                            "description": "The new numeric value to assign to the account. Debit is positive, Credit is negative (e.g. Sales is negative, Cash is positive)."
                        }
                    },
                    "required": ["company_id", "account", "new_value"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_financial_python_analysis",
                "description": "Execute custom python code to model financial cash flows, run ratios, or perform numeric analysis. The local namespace has access to 'generate_balance_sheet', 'generate_income_statement', and 'run_consolidation' helpers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The python code snippet to run. Be sure to use 'print()' to output the final result so it can be captured in stdout."
                        }
                    },
                    "required": ["code"]
                }
            }
        }
    ]

def execute_finance_tool_call(function_name, function_args, update_state_callback=None):
    """
    Execute a financial tool call and return structured results.
    Triggers a callback to notify the server of updated visual state.
    """
    orchestrator = AgenticOrchestrator()
    
    try:
        if function_name == "get_financial_statements":
            cid = function_args.get("company_id")
            period = function_args.get("period", "FY25_actual")
            
            # Execute through orchestrator
            recon_results = orchestrator.execute_task("reconcile_ledgers", {"company_id": cid, "period": period})
            
            p_l = generate_income_statement(cid, period)
            bs = generate_balance_sheet(cid, period)
            cf = generate_cash_flow_statement(cid, period)
            
            result = {
                "status": "success",
                "company_id": cid,
                "period": period,
                "income_statement": p_l,
                "balance_sheet": bs,
                "cash_flow": cf,
                "ledger_checks": recon_results["ledger_balances"].get(cid, {})
            }
            if update_state_callback:
                update_state_callback("reports", cid, result)
            return result
            
        elif function_name == "run_group_consolidation":
            period = function_args.get("period", "FY25_actual")
            
            # Execute through orchestrator
            result = orchestrator.execute_task("group_consolidation", {"period": period})
            
            formatted_result = {
                "status": "success",
                "period": period,
                "consolidation_matrix": result
            }
            if update_state_callback:
                update_state_callback("consolidation", "group", formatted_result)
            return formatted_result
            
        elif function_name == "review_financial_records":
            cid = function_args.get("company_id", "parent_nv")
            
            # Execute through orchestrator tasks
            orchestrator.execute_task("compliance_audit", {"company_id": cid})
            review_results = orchestrator.execute_task("strategic_cfo_review", {"company_id": cid})
            
            result = {
                "status": "success",
                "company_id": cid,
                "review": review_results
            }
            if update_state_callback:
                update_state_callback("review", cid, result)
            return result
            
        elif function_name == "update_financial_figure":
            cid = function_args.get("company_id")
            period = function_args.get("period", "FY25_actual")
            account = function_args.get("account")
            new_value = float(function_args.get("new_value"))
            
            from finance.data_provider import get_raw_data, save_raw_data
            data = get_raw_data()
            if cid in data["companies"] and period in data["companies"][cid]["trial_balance"]:
                data["companies"][cid]["trial_balance"][period][account] = new_value
                save_raw_data(data)
                
                # Log action to orchestrator
                ExecutionLog.log("Chief CFO", "Direct Data Adjustment", f"Adjusted {account} of {cid} in {period} to {new_value:,.2f}.")
                
                # Recalculate statements and review
                recon_results = orchestrator.execute_task("reconcile_ledgers", {"company_id": cid, "period": period})
                p_l = generate_income_statement(cid, period)
                bs = generate_balance_sheet(cid, period)
                cf = generate_cash_flow_statement(cid, period)
                
                result = {
                    "status": "success",
                    "company_id": cid,
                    "period": period,
                    "account": account,
                    "new_value": new_value,
                    "message": f"Successfully updated '{account}' for company '{cid}' ({period}) to {new_value:,.2f}.",
                    "income_statement": p_l,
                    "balance_sheet": bs,
                    "cash_flow": cf
                }
                
                if update_state_callback:
                    update_state_callback("data_update", cid, result)
                return result
            else:
                return {"status": "error", "message": "Company or period not found in database."}
            
        elif function_name == "run_financial_python_analysis":
            code = function_args.get("code", "")
            
            # Enforce limits & sandboxing
            if len(code) > 4000:
                return {"status": "error", "message": "Code exceeds maximum allowed length of 4000 characters."}
                
            # Log action to orchestrator
            ExecutionLog.log("Chief CFO", "Run Python Code Analysis", f"Executing safe mathematical scripting model.")
            
            # Redirect stdout to capture prints
            old_stdout = sys.stdout
            redirected_output = sys.stdout = io.StringIO()
            
            try:
                # Setup safe local execution environment
                safe_namespace = {
                    "generate_balance_sheet": generate_balance_sheet,
                    "generate_income_statement": generate_income_statement,
                    "generate_cash_flow_statement": generate_cash_flow_statement,
                    "run_consolidation": run_consolidation,
                    "calculate_financial_ratios": calculate_financial_ratios,
                    "json": json,
                }
                
                # Execute user code safely
                # No imports, no file operations, no sys/os allowed
                # Replaces __builtins__ with safe whitelisted builtins
                safe_builtins = {
                    "abs": abs, "round": round, "sum": sum, "min": min, "max": max,
                    "len": len, "range": range, "list": list, "dict": dict, "set": set,
                    "str": str, "int": int, "float": float, "print": print, "bool": bool,
                    "enumerate": enumerate, "zip": zip
                }
                
                # Inject restricted scope
                exec(code, {"__builtins__": safe_builtins}, safe_namespace)
                output = redirected_output.getvalue()
                
                return {
                    "status": "success",
                    "output": output
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Execution error: {str(e)}",
                    "traceback": traceback.format_exc()
                }
            finally:
                sys.stdout = old_stdout
                
        else:
            return {"status": "error", "message": f"Unknown financial tool '{function_name}'"}
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Internal error executing tool '{function_name}': {str(e)}"
        }
