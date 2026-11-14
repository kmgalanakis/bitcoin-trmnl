"""Tests for the wallet service. Run: .venv/bin/python -m unittest -v test_app.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import app  # noqa: E402

# Public BIP84 test vector account key (mnemonic "abandon ... about"). Holds no real secret.
ZPUB = "zpub6rFR7y4Q2AijBEqTUquhVz398htDFrtymD9xYYfG1m4wAcvPhXNfE3EfH1r1ADqtfSdVCToUG868RvUUkgDKf31mGDtKsAYz2oz2AGutZYs"
EXTERNAL = "bc1qexternal000000000000000000000000000000"


def stats(funded=0, spent=0, txs=0, m_funded=0, m_spent=0, m_txs=0):
    return {
        "chain_stats": {"funded_txo_sum": funded, "spent_txo_sum": spent, "tx_count": txs},
        "mempool_stats": {"funded_txo_sum": m_funded, "spent_txo_sum": m_spent, "tx_count": m_txs},
    }


def tx(txid, vin, vout, time=None):
    return {
        "txid": txid,
        "vin": [{"prevout": {"scriptpubkey_address": a, "value": v}} for a, v in vin],
        "vout": [{"scriptpubkey_address": a, "value": v} for a, v in vout],
        "status": {"confirmed": time is not None, "block_time": time} if time else {"confirmed": False},
    }


class FakeChain:
    """A wallet with used addresses at receive 0, 3 and 15 and change 0, with gaps under 20."""

    def __init__(self):
        r0, r3, r15 = (app.derive_address(ZPUB, 0, i) for i in (0, 3, 15))
        c0 = app.derive_address(ZPUB, 1, 0)
        t1 = tx("t1", [(EXTERNAL, 100500)], [(r0, 100000)], time=100)
        t2 = tx("t2", [(r0, 100000)], [(EXTERNAL, 30000), (c0, 69000)], time=200)
        t3 = tx("t3", [(EXTERNAL, 50300)], [(r3, 50000)], time=300)
        t4 = tx("t4", [(c0, 69000)], [(r15, 68500)])  # self-transfer, unconfirmed, fee 500
        self.stats = {
            r0: stats(100000, 100000, 2),
            r3: stats(50000, 0, 1),
            r15: stats(m_funded=68500, m_txs=1),
            c0: stats(69000, 0, 1, m_spent=69000, m_txs=1),
        }
        self.txs = {r0: [t2, t1], r3: [t3], r15: [t4], c0: [t4, t2]}
        self.calls = 0
        self.fail = False

    def __call__(self, path):
        self.calls += 1
        if self.fail:
            raise OSError("mempool down")
        parts = path.strip("/").split("/")
        address = parts[1]
        if len(parts) == 3:
            return self.txs.get(address, [])
        return self.stats.get(address, stats())


class DeriveTest(unittest.TestCase):
    def test_bip84_vectors(self):
        self.assertEqual(app.derive_address(ZPUB, 0, 0), "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu")
        self.assertEqual(app.derive_address(ZPUB, 0, 1), "bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g")
        self.assertEqual(app.derive_address(ZPUB, 1, 0), "bc1q8c6fshw2dlwun7ekn9qwf37cu2rn755upcp6el")

    def test_xpub_version_gives_same_addresses(self):
        xpub = app.to_xpub(ZPUB)
        self.assertTrue(xpub.startswith("xpub"))
        self.assertEqual(app.derive_address(xpub, 0, 0), "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu")


class ScanTest(unittest.TestCase):
    def setUp(self):
        self.result = app.scan(ZPUB, FakeChain(), gap_limit=20, max_txs=10)

    def test_finds_addresses_past_short_gaps(self):
        self.assertEqual(self.result["addresses_used"], 4)

    def test_balance_includes_pending(self):
        self.assertEqual(self.result["balance_sats"], 118500)
        self.assertEqual(self.result["pending_sats"], -500)

    def test_transactions_are_netted_deduped_and_ordered(self):
        txs = self.result["txs"]
        self.assertEqual(self.result["tx_count"], 4)
        self.assertEqual([t["sats"] for t in txs], [-500, 50000, -31000, 100000])
        self.assertEqual([t["confirmed"] for t in txs], [False, True, True, True])
        self.assertIsNone(txs[0]["time"])
        self.assertEqual(txs[1]["time"], 300)

    def test_response_hides_addresses_and_key(self):
        text = repr(self.result)
        self.assertNotIn("bc1q", text)
        self.assertNotIn(ZPUB[:12], text)

    def test_max_txs_limits_the_list(self):
        self.assertEqual(len(app.scan(ZPUB, FakeChain(), max_txs=2)["txs"]), 2)


class WalletTest(unittest.TestCase):
    def test_before_the_first_scan_returns_502(self):
        status, body = app.Wallet(ZPUB, FakeChain()).get()
        self.assertEqual(status, 502)
        self.assertIn("first scan", body["error"])

    def test_first_failure_returns_502(self):
        chain = FakeChain()
        chain.fail = True
        wallet = app.Wallet(ZPUB, chain)
        wallet.refresh()
        status, body = wallet.get()
        self.assertEqual(status, 502)
        self.assertIn("error", body)

    def test_get_never_scans(self):
        chain = FakeChain()
        wallet = app.Wallet(ZPUB, chain)
        wallet.refresh()
        calls = chain.calls
        self.assertEqual(wallet.get()[0], 200)
        self.assertEqual(chain.calls, calls)

    def test_failed_rescan_keeps_the_last_scan(self):
        chain = FakeChain()
        wallet = app.Wallet(ZPUB, chain)
        wallet.refresh()
        chain.fail = True
        wallet.refresh()
        status, body = wallet.get()
        self.assertEqual(status, 200)
        self.assertEqual(body["balance_sats"], 118500)

    def test_invalid_xpub_returns_502_without_echoing_it(self):
        secret = "xpubNOTAREALKEY123"
        wallet = app.Wallet(secret, FakeChain())
        wallet.refresh()
        status, body = wallet.get()
        self.assertEqual(status, 502)
        self.assertNotIn(secret, repr(body))

    def test_missing_xpub_returns_502(self):
        wallet = app.Wallet("", FakeChain())
        wallet.refresh()
        status, body = wallet.get()
        self.assertEqual(status, 502)
        self.assertIn("XPUB", body["error"])


class RetryTest(unittest.TestCase):
    def test_retries_after_429_with_growing_waits(self):
        import urllib.error
        attempts, waits = [0], []

        def flaky(path):
            attempts[0] += 1
            if attempts[0] < 3:
                raise urllib.error.HTTPError(path, 429, "Too Many Requests", {}, None)
            return {"ok": path}

        fetch = app.polite(flaky, delay=0.5, sleep=waits.append)
        self.assertEqual(fetch("/x"), {"ok": "/x"})
        self.assertEqual(attempts[0], 3)
        self.assertEqual(waits, [0.5, 5, 0.5, 10, 0.5])

    def test_gives_up_after_the_last_retry(self):
        import urllib.error

        def always_429(path):
            raise urllib.error.HTTPError(path, 429, "Too Many Requests", {}, None)

        fetch = app.polite(always_429, delay=0, sleep=lambda s: None, retries=3)
        with self.assertRaises(urllib.error.HTTPError):
            fetch("/x")

    def test_other_errors_are_not_retried(self):
        import urllib.error
        attempts = [0]

        def not_found(path):
            attempts[0] += 1
            raise urllib.error.HTTPError(path, 400, "Bad Request", {}, None)

        with self.assertRaises(urllib.error.HTTPError):
            app.polite(not_found, delay=0, sleep=lambda s: None)("/x")
        self.assertEqual(attempts[0], 1)


if __name__ == "__main__":
    unittest.main()
