# Financial Transaction Orchestration

A simple base project that coordinates a money transfer as a multi-step
workflow using the **saga pattern**: if any step fails, completed steps are
undone in reverse order so balances stay consistent.

## Workflow
validate -> fraud_check -> debit_source -> credit_destination -> notify

## Files
- `orchestrator.py` - Ledger, Transaction, Step and Orchestrator
- `demo.py` - runs sample scenarios and prints balances + audit trail
- `test_orchestrator.py` - unit tests

## Run
```
python demo.py
python -m unittest -v
```

## Key ideas
- Compensation: every state-changing step has an undo action.
- Idempotency: the same `idempotency_key` never executes twice.
- Audit log: every step and outcome is recorded.
- Decimal is used for money (never float).

## Ideas to extend
- Persist ledger and audit log in a database
- Add retries with backoff and a message queue
- Expose a REST API (FastAPI/Flask)
- Add more steps (currency conversion, KYC, fee calculation)
