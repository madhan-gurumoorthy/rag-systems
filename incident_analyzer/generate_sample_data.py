"""
generate_sample_data.py
-----------------------
Creates a sample incidents.xlsx fixture with realistic data for testing.
Run once before running main.py:

    python generate_sample_data.py
"""

import random
from datetime import datetime, timedelta

import pandas as pd

random.seed(42)

TEMPLATES = [
    # (short_description, description, category_hint)
    ("User unable to login", "Authentication failure due to expired SSO token", "auth"),
    ("Benefit eligibility check failing", "Member not found in eligibility database", "eligibility"),
    ("Daily feed not received", "SFTP file ingestion failed for daily benefit feed", "feed"),
    ("Portal page not loading", "White screen reported on member portal", "ui"),
    ("API timeout on claims endpoint", "Downstream REST call to claims API returning 504", "api"),
    ("Data sync mismatch detected", "Duplicate records found after replication sync", "sync"),
    ("Email notification not sent", "Alert email failed to deliver to 150 members", "notification"),
    ("Deployment rollback triggered", "Config mismatch caused pipeline failure in prod", "config"),
    ("Slow response on search", "Latency spike > 5s on member search endpoint", "performance"),
    ("Coverage lapsed for member", "Benefit coverage lapsed due to enrollment failure", "eligibility"),
    ("ETL job failed overnight", "ETL import error on nightly data import job", "feed"),
    ("Unauthorized access attempt", "403 error returned for role-based access", "auth"),
]

STATES = ["Resolved", "In Progress", "Closed", "New", "On Hold"]

rows = []
start_date = datetime(2025, 1, 1)

for _ in range(300):
    template = random.choice(TEMPLATES)
    delta_days = random.randint(0, 364)
    created_on = start_date + timedelta(days=delta_days, hours=random.randint(0, 23))
    rows.append({
        "sys_created_on": created_on.strftime("%Y-%m-%d %H:%M:%S"),
        "short_description": template[0],
        "description": template[1],
        "state": random.choice(STATES),
    })

df = pd.DataFrame(rows).sort_values("sys_created_on").reset_index(drop=True)
df.to_excel("incidents.xlsx", index=False, engine="openpyxl")
print(f"✅ Created incidents.xlsx with {len(df)} rows.")
