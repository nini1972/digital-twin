import os
import json

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "financials")
FILE_PATH = os.path.join(DATA_DIR, "solaria_group.json")

def get_raw_data():
    """Load financial data from the JSON file."""
    if not os.path.exists(FILE_PATH):
        raise FileNotFoundError(f"Financial database file not found at: {FILE_PATH}")
    
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_raw_data(data):
    """Save updated financial data back to the JSON file."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def get_companies():
    """Retrieve companies dictionary."""
    return get_raw_data().get("companies", {})

def get_company(company_id):
    """Retrieve a specific company's info and trial balances."""
    companies = get_companies()
    if company_id not in companies:
        raise ValueError(f"Company '{company_id}' not found.")
    return companies[company_id]

def get_exchange_rates():
    """Retrieve USD to EUR exchange rates."""
    return get_raw_data().get("group_metadata", {}).get("exchange_rates", {
        "USD_EUR_closing": 0.91,
        "USD_EUR_average": 0.93
    })

def get_intercompany_transactions():
    """Retrieve the intercompany transactions list."""
    return get_raw_data().get("intercompany_transactions", [])

def get_compliance_issues():
    """Retrieve standard compliance issues list."""
    return get_raw_data().get("compliance_issues", [])
