"""Tests for the wallet service. Run: service/.venv/bin/python -m unittest -v service/test_app.py"""
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
    def test_first_failure_returns_502(self):
        chain = FakeChain()
        chain.fail = True
        status, body = app.Wallet(ZPUB, chain).get()
        self.assertEqual(status, 502)
        self.assertIn("error", body)

    def test_failed_rescan_serves_the_cached_scan(self):
        now = [1000.0]
        chain = FakeChain()
        wallet = app.Wallet(ZPUB, chain, cache_seconds=300, clock=lambda: now[0])
        status, first = wallet.get()
        self.assertEqual(status, 200)
        calls = chain.calls
        self.assertEqual(wallet.get(), (200, first))
        self.assertEqual(chain.calls, calls, "second call within the cache window must not scan")
        now[0] += 301
        chain.fail = True
        status, body = wallet.get()
        self.assertEqual(status, 200)
        self.assertEqual(body["balance_sats"], 118500)

    def test_invalid_xpub_returns_502_without_echoing_it(self):
        secret = "xpubNOTAREALKEY123"
        status, body = app.Wallet(secret, FakeChain()).get()
        self.assertEqual(status, 502)
        self.assertNotIn(secret, repr(body))

    def test_missing_xpub_returns_502(self):
        status, body = app.Wallet("", FakeChain()).get()
        self.assertEqual(status, 502)
        self.assertIn("XPUB", body["error"])


if __name__ == "__main__":
    unittest.main()
