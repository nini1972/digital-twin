import datetime
from typing import List, Dict, Any, Optional

class ExecutionLog:
    _logs: List[Dict[str, Any]] = []
    
    @classmethod
    def clear(cls):
        cls._logs.clear()
        
    @classmethod
    def log(cls, agent_name: str, action: str, details: str, status: str = "success"):
        cls._logs.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "agent": agent_name,
            "action": action,
            "details": details,
            "status": status
        })
        
    @classmethod
    def get_logs(cls) -> List[Dict[str, Any]]:
        return cls._logs

class FinanceAgent:
    def __init__(self, name: str, role: str, description: str, instructions: str):
        self.name = name
        self.role = role
        self.description = description
        self.instructions = instructions

class FinanceTask:
    def __init__(self, name: str, agent_name: str, description: str):
        self.name = name
        self.agent_name = agent_name
        self.description = description

class AgenticOrchestrator:
    def __init__(self):
        self.agents: Dict[str, FinanceAgent] = {}
        self.tasks: Dict[str, FinanceTask] = {}
        self._initialize_default_agents()
        
    def register_agent(self, agent: FinanceAgent):
        self.agents[agent.name] = agent
        
    def register_task(self, task: FinanceTask):
        self.tasks[task.name] = task
        
    def _initialize_default_agents(self):
        # Register Scout
        self.register_agent(FinanceAgent(
            name="Scout",
            role="Finance Scout & Ledger Auditor",
            description="Performs initial trial balance scans, locates discrepancies, and matches intercompany transactions.",
            instructions="Scan all trial balances. Ensure assets match liabilities and equity. Verify that intercompany transactions have matching entries in both counterparties."
        ))
        # Register Consolidator
        self.register_agent(FinanceAgent(
            name="Consolidator",
            role="Group Consolidation Specialist",
            description="Aggregates subsidiary financials, translates foreign currencies, and applies intercompany eliminations.",
            instructions="For foreign subsidiaries, translate assets/liabilities at closing rate and P&L at average rate. Eliminate intercompany sales, fees, and receivables. Compute Non-Controlling Interest (NCI)."
        ))
        # Register Auditor
        self.register_agent(FinanceAgent(
            name="Auditor",
            role="Tax & Accounting Compliance Auditor",
            description="Audits records against accounting standard violations (BGAAP/IFRS) and evaluates financial ratios.",
            instructions="Verify compliance of capitalized development/research costs. Calculate interest coverage, liquidity ratios, and debt-to-equity leverage risks."
        ))
        # Register Chief CFO (Dominique)
        self.register_agent(FinanceAgent(
            name="Chief CFO",
            role="Chief AI Financial Specialist",
            description="Coordinates strategic financial review, runs variance analysis, and synthesizes executive reports.",
            instructions="Decompose the user's queries into tasks, delegate to other agents, compile the results, and deliver high-level insights."
        ))
        
        # Register tasks
        self.register_task(FinanceTask("reconcile_ledgers", "Scout", "Runs full checks on individual ledger accounts and flags imbalances."))
        self.register_task(FinanceTask("group_consolidation", "Consolidator", "Executes multi-subsidiary financial statement consolidation."))
        self.register_task(FinanceTask("compliance_audit", "Auditor", "Audits IAS/IFRS compliance and runs comprehensive ratio analysis."))
        self.register_task(FinanceTask("strategic_cfo_review", "Chief CFO", "Summarizes the overall group performance, reviews variances, and provides professional advice."))

    def execute_task(self, task_name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        if params is None:
            params = {}
        if task_name not in self.tasks:
            raise ValueError(f"Task '{task_name}' is not registered.")
        
        task = self.tasks[task_name]
        agent = self.agents[task.agent_name]
        
        ExecutionLog.log(agent.name, f"Starting task: {task_name}", f"Instructions: {agent.instructions}")
        
        try:
            result = {}
            if task_name == "reconcile_ledgers":
                from finance.review import perform_intercompany_reconciliation
                from finance.reports import generate_balance_sheet
                from finance.data_provider import get_companies
                
                recon = perform_intercompany_reconciliation()
                companies = get_companies()
                balances = {}
                for cid in companies:
                    try:
                        bs = generate_balance_sheet(cid)
                        balances[cid] = {
                            "name": bs["company_name"],
                            "is_balanced": bs["is_balanced"],
                            "discrepancy": bs["discrepancy"]
                        }
                    except Exception as e:
                        balances[cid] = {"error": str(e)}
                        
                result = {
                    "intercompany_reconciliation": recon,
                    "ledger_balances": balances
                }
                ExecutionLog.log(agent.name, f"Completed task: {task_name}", f"Scanned {len(companies)} companies. Found {len(recon['mismatches'])} intercompany discrepancies.")
                
            elif task_name == "group_consolidation":
                from finance.consolidation import run_consolidation
                period = params.get("period", "FY25_actual")
                consolidation_result = run_consolidation(period)
                result = consolidation_result
                ExecutionLog.log(agent.name, f"Completed task: {task_name}", f"Consolidation complete for {period}. Final consolidated assets: €{consolidation_result['balance_sheet']['assets']['Total Assets']:,.2f}.")
                
            elif task_name == "compliance_audit":
                from finance.review import audit_compliance_issues, calculate_financial_ratios
                from finance.data_provider import get_companies
                
                comp_issues = audit_compliance_issues()
                companies = get_companies()
                ratios = {}
                for cid in companies:
                    try:
                        ratios[cid] = calculate_financial_ratios(cid)
                    except Exception as e:
                        ratios[cid] = {"error": str(e)}
                        
                result = {
                    "compliance_issues": comp_issues,
                    "financial_ratios": ratios
                }
                ExecutionLog.log(agent.name, f"Completed task: {task_name}", f"Audit completed. Found {len(comp_issues)} active compliance warnings and generated financial health checks.")
                
            elif task_name == "strategic_cfo_review":
                from finance.review import run_variance_analysis, run_comprehensive_review
                company_id = params.get("company_id", "parent_nv")
                review_data = run_comprehensive_review(company_id)
                result = review_data
                ExecutionLog.log(agent.name, f"Completed task: {task_name}", f"Strategic review complete for {company_id}. Generated year-over-year commentary.")
                
            else:
                raise NotImplementedError(f"Task '{task_name}' execution logic not implemented.")
                
            return result
        except Exception as e:
            ExecutionLog.log(agent.name, f"Failed task: {task_name}", f"Error: {str(e)}", status="failed")
            raise e
