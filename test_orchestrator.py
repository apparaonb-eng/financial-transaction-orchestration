import unittest
from decimal import Decimal

from orchestrator import Ledger, Orchestrator, Transaction


def make():
    ledger = Ledger()
    ledger.add_account("A", 1000)
    ledger.add_account("B", 100)
    return ledger, Orchestrator(ledger)


class TestOrchestrator(unittest.TestCase):
    def test_success_moves_money(self):
        ledger, orch = make()
        t = orch.execute(Transaction("A", "B", Decimal("300")))
        self.assertEqual(t.status, "COMPLETED")
        self.assertEqual(ledger.accounts["A"].balance, Decimal("700"))
        self.assertEqual(ledger.accounts["B"].balance, Decimal("400"))

    def test_insufficient_funds_rolls_back(self):
        ledger, orch = make()
        t = orch.execute(Transaction("B", "A", Decimal("500")))
        self.assertEqual(t.status, "ROLLED_BACK")
        self.assertEqual(ledger.accounts["B"].balance, Decimal("100"))

    def test_failure_after_debit_is_compensated(self):
        ledger, orch = make()

        def boom(msg):
            raise RuntimeError("notification down")

        orch.notifier = boom
        t = orch.execute(Transaction("A", "B", Decimal("200")))
        self.assertEqual(t.status, "ROLLED_BACK")
        self.assertEqual(ledger.accounts["A"].balance, Decimal("1000"))
        self.assertEqual(ledger.accounts["B"].balance, Decimal("100"))

    def test_idempotency(self):
        ledger, orch = make()
        t1 = Transaction("A", "B", Decimal("100"), idempotency_key="k1")
        orch.execute(t1)
        orch.execute(Transaction("A", "B", Decimal("100"), idempotency_key="k1"))
        self.assertEqual(ledger.accounts["A"].balance, Decimal("900"))

    def test_invalid_amount(self):
        _, orch = make()
        self.assertEqual(orch.execute(Transaction("A", "B", Decimal("-5"))).status, "ROLLED_BACK")


if __name__ == "__main__":
    unittest.main()
