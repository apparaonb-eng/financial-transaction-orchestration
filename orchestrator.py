"""Financial Transaction Orchestration - simple base project.

A saga-style orchestrator: a transfer runs as an ordered list of steps.
If any step fails, the steps that already succeeded are compensated
(rolled back) in reverse order. Includes idempotency keys and an audit log.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


class TransactionError(Exception):
    pass


@dataclass
class Account:
    account_id: str
    balance: Decimal
    daily_limit: Decimal = Decimal("10000")


@dataclass
class Transaction:
    source: str
    destination: str
    amount: Decimal
    idempotency_key: str = field(default_factory=lambda: str(uuid.uuid4()))
    txn_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    status: str = "PENDING"  # PENDING -> COMPLETED | ROLLED_BACK
    error: str = ""


class Ledger:
    """In-memory account store with an audit trail."""

    def __init__(self):
        self.accounts = {}
        self.audit = []

    def add_account(self, account_id, balance, daily_limit="10000"):
        self.accounts[account_id] = Account(account_id, Decimal(str(balance)), Decimal(daily_limit))

    def log(self, txn_id, event, detail=""):
        self.audit.append({"time": datetime.now().isoformat(timespec="seconds"),
                           "txn": txn_id, "event": event, "detail": detail})

    def get(self, account_id):
        if account_id not in self.accounts:
            raise TransactionError(f"Unknown account {account_id}")
        return self.accounts[account_id]


class Step:
    """One unit of work plus the action that undoes it."""

    def __init__(self, name, action, compensate=None):
        self.name = name
        self.action = action
        self.compensate = compensate


class Orchestrator:
    def __init__(self, ledger, notifier=None):
        self.ledger = ledger
        self.notifier = notifier or (lambda msg: None)
        self._processed = {}  # idempotency_key -> Transaction

    # ---- steps -------------------------------------------------------
    def _validate(self, t):
        if t.amount <= 0:
            raise TransactionError("Amount must be positive")
        if t.source == t.destination:
            raise TransactionError("Source and destination must differ")
        src = self.ledger.get(t.source)
        self.ledger.get(t.destination)
        if t.amount > src.daily_limit:
            raise TransactionError("Amount exceeds daily limit")

    def _fraud_check(self, t):
        if t.amount >= Decimal("9000"):
            raise TransactionError("Flagged by fraud check (high amount)")

    def _debit(self, t):
        src = self.ledger.get(t.source)
        if src.balance < t.amount:
            raise TransactionError("Insufficient funds")
        src.balance -= t.amount

    def _undo_debit(self, t):
        self.ledger.get(t.source).balance += t.amount

    def _credit(self, t):
        self.ledger.get(t.destination).balance += t.amount

    def _undo_credit(self, t):
        self.ledger.get(t.destination).balance -= t.amount

    def _notify(self, t):
        self.notifier(f"Transfer {t.txn_id}: {t.amount} from {t.source} to {t.destination}")

    def build_steps(self):
        return [
            Step("validate", self._validate),
            Step("fraud_check", self._fraud_check),
            Step("debit_source", self._debit, self._undo_debit),
            Step("credit_destination", self._credit, self._undo_credit),
            Step("notify", self._notify),
        ]

    # ---- orchestration -----------------------------------------------
    def execute(self, t):
        # Idempotency: the same key returns the original result, never re-runs.
        if t.idempotency_key in self._processed:
            return self._processed[t.idempotency_key]

        self.ledger.log(t.txn_id, "STARTED", f"{t.source}->{t.destination} {t.amount}")
        done = []
        try:
            for step in self.build_steps():
                step.action(t)
                done.append(step)
                self.ledger.log(t.txn_id, f"STEP_OK:{step.name}")
            t.status = "COMPLETED"
        except Exception as exc:  # noqa: BLE001 - any failure triggers rollback
            t.error = str(exc)
            self.ledger.log(t.txn_id, "STEP_FAILED", t.error)
            for step in reversed(done):
                if step.compensate:
                    step.compensate(t)
                    self.ledger.log(t.txn_id, f"COMPENSATED:{step.name}")
            t.status = "ROLLED_BACK"

        self.ledger.log(t.txn_id, t.status)
        self._processed[t.idempotency_key] = t
        return t
