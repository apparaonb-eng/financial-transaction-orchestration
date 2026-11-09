from decimal import Decimal

from orchestrator import Ledger, Orchestrator, Transaction

ledger = Ledger()
ledger.add_account("ACC-A", 5000)
ledger.add_account("ACC-B", 1000)

orch = Orchestrator(ledger, notifier=lambda m: print("  [notify]", m))

scenarios = [
    ("Normal transfer", Transaction("ACC-A", "ACC-B", Decimal("1500"))),
    ("Insufficient funds", Transaction("ACC-B", "ACC-A", Decimal("8000"))),
    ("Fraud flag", Transaction("ACC-A", "ACC-B", Decimal("9500"))),
    ("Unknown account", Transaction("ACC-A", "ACC-X", Decimal("10"))),
]

for label, txn in scenarios:
    result = orch.execute(txn)
    print(f"{label}: {result.status} {result.error}")

# Idempotency: replaying the first request does not move money again.
replay = Transaction("ACC-A", "ACC-B", Decimal("1500"), idempotency_key=scenarios[0][1].idempotency_key)
print("Replay:", orch.execute(replay).status, "(same result, no double charge)")

print("\nBalances:", {k: str(v.balance) for k, v in ledger.accounts.items()})
print("\nAudit trail:")
for e in ledger.audit:
    print(f"  {e['txn']} {e['event']} {e['detail']}")
