import os
import sys
import asyncio
import unittest
import shutil

# Add backend directory to path to ensure imports work in tests
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from context import prompt
from finance_tools import execute_finance_tool_call
from server import get_all_skills, execute_midnight_audit, active_finance_state

class TestHermesIntegration(unittest.TestCase):
    
    def test_sovereign_soul_prompt_generation(self):
        """Verify that Sovereign SOUL and Tier 1 grounding memories are compiled into the system prompt."""
        sys_prompt = prompt(user_query="reconcile Flanders receivables")
        
        # Assert sovereign SOUL is injected
        self.assertTrue("Sovereignty Layer (SOUL)" in sys_prompt or "SOUL" in sys_prompt)
        
        # Assert Tier 1 memory is injected
        self.assertTrue("Group Structural Blueprint" in sys_prompt)
        self.assertTrue("CFO Accounting Policies" in sys_prompt)
        
        # Assert database grounding numbers are injected
        self.assertTrue("Group Entities" in sys_prompt)
        self.assertTrue("Parent NV" in sys_prompt)

    def test_skill_compiler_tool(self):
        """Verify that the create_or_update_playbook tool writes a clean Markdown playbook with YAML frontmatter."""
        skills_dir = os.path.join(backend_dir, "finance", "skills")
        test_skill_name = "test_receivables_reconciliation"
        test_file_path = os.path.join(skills_dir, f"{test_skill_name}.md")
        
        # Clean up if exists from prior runs
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
            
        args = {
            "name": test_skill_name,
            "description": "Verify and resolve cross-border intercompany balances for receivables.",
            "category": "accounting-consolidation",
            "requires_tools": ["get_financial_statements", "review_financial_records"],
            "procedure": "1. Retrieve parent receivable ledger.\n2. Cross-reference Flanders payable.\n3. Spot variance."
        }
        
        # Run compiler tool
        result = execute_finance_tool_call(
            function_name="create_or_update_playbook",
            function_args=args,
            update_state_callback=None
        )
        
        self.assertEqual(result["status"], "success")
        self.assertTrue(os.path.exists(test_file_path))
        
        # Read and assert contents
        with open(test_file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        self.assertTrue("name: test_receivables_reconciliation" in content)
        self.assertTrue("category: accounting-consolidation" in content)
        self.assertTrue("requires_tools: [get_financial_statements, review_financial_records]" in content)
        self.assertTrue("## Procedure" in content
)
        self.assertTrue("1. Retrieve parent receivable ledger." in content)
        
        # Clean up
        if os.path.exists(test_file_path):
            os.remove(test_file_path)

    def test_skills_listing(self):
        """Verify that get_all_skills accurately parses playbooks from disk."""
        skills = get_all_skills()
        self.assertTrue(len(skills) > 0)
        
        # Verify that default playbooks exist
        playbook_ids = [s["id"] for s in skills]
        self.assertTrue("compliance_audit" in playbook_ids)
        self.assertTrue("group_consolidation" in playbook_ids)
        self.assertTrue("reconcile_ledgers" in playbook_ids)

    def test_midnight_audit_run(self):
        """Verify that the simulated midnight audit schedules, executes, and builds robust alert packages."""
        # Use asyncio to run the async execute_midnight_audit
        asyncio.run(execute_midnight_audit())
        
        audit_state = active_finance_state.get("midnight_audit_run")
        self.assertIsNotNone(audit_state)
        self.assertEqual(audit_state["status"], "completed")
        self.assertEqual(audit_state["violations_found"], 2)
        
        # Assert simulated alerts exist
        alerts = audit_state["alerts"]
        alert_ids = [a["id"] for a in alerts]
        self.assertTrue("alert_ias38" in alert_ids)
        self.assertTrue("alert_intercompany_mismatch" in alert_ids)
        
        # Assert platform integrations are generated
        integrations = audit_state["integrations"]
        self.assertTrue("teams" in integrations)
        self.assertTrue("outlook" in integrations)
        self.assertTrue("whatsapp" in integrations)
        
        self.assertTrue("AdaptiveCard" in integrations["teams"]["adaptive_card"]["type"])
        self.assertTrue("⚠️ Solaria Group Ledger Audit:" in integrations["outlook"]["subject"])
        self.assertTrue("Dominique's Twin Midnight Audit Summary" in integrations["whatsapp"]["message"])

if __name__ == "__main__":
    unittest.main()
