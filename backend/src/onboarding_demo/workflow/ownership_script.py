"""The ownership script the agent runs in Code Interpreter.

The model is asked to write this itself. This reference version is what the fake model
returns, and what the workflow falls back to if the model's code does not run.
"""
REFERENCE_SCRIPT = '''
import csv, json

rows = list(csv.DictReader(open("shareholders.csv")))
owners_of = {}
for r in rows:
    owners_of.setdefault(r["owned"], []).append((r["owner"], float(r["percent"])))

totals = {}
def walk(entity, share):
    for owner, percent in owners_of.get(entity, []):
        part = share * percent / 100
        if owner in owners_of:
            walk(owner, part)
        else:
            totals[owner] = round(totals.get(owner, 0) + part, 4)

walk("__COMPANY__", 100)
print(json.dumps(totals))
'''


def reference_script(company: str) -> str:
    return REFERENCE_SCRIPT.replace("__COMPANY__", company)


def shareholders_csv(holdings) -> str:
    lines = ["owner,owned,percent"] + [f"{h.owner},{h.owned},{h.percent}" for h in holdings]
    return "\n".join(lines) + "\n"
