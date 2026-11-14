"""Bitcoin wallet sidecar for the Terminus extension.

Reads one account's extended public key (xpub) from the XPUB environment variable,
finds the account's used native SegWit addresses through the mempool.space API,
and serves the total balance and recent transactions as JSON at /wallet.

The xpub never leaves this process: it is not logged and not returned.
"""
import json
import logging
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from embit import bip32, script
from embit.networks import NETWORKS

MAINNET = NETWORKS["main"]
log = logging.getLogger("bitcoin-wallet")


# ---------- derivation ----------
def _account_key(xpub):
    if not xpub:
        raise ValueError("XPUB is not set.")
    try:
        key = bip32.HDKey.from_string(xpub.strip())
    except Exception:
        raise ValueError("XPUB is not a valid extended public key.") from None
    if key.is_private:
        raise ValueError("XPUB holds a private key. Use the account's public key (xpub) only.")
    return key


def to_xpub(key_string):
    """Returns the same key with the plain xpub version, e.g. for a zpub."""
    key = _account_key(key_string)
    key.version = MAINNET["xpub"]
    return key.to_base58()


def derive_address(xpub, chain, index, _key=None):
    """Native SegWit (P2WPKH) mainnet address at <chain>/<index> below the account key."""
    key = _key or _account_key(xpub)
    return script.p2wpkh(key.derive([chain, index])).address(MAINNET)


# ---------- scan ----------
def _sum(stats, side):
    s = stats.get(side) or {}
    return (s.get("funded_txo_sum") or 0) - (s.get("spent_txo_sum") or 0)


def _tx_count(stats):
    return sum((stats.get(side) or {}).get("tx_count") or 0 for side in ("chain_stats", "mempool_stats"))


def net_txs(txs, wallet_addresses, limit):
    """Net effect of each unique transaction on the whole wallet, unconfirmed first, then newest first."""
    unique = {}
    for t in txs:
        unique.setdefault(t["txid"], t)
    rows = []
    for t in unique.values():
        sats = sum(o.get("value", 0) for o in t.get("vout", []) if o.get("scriptpubkey_address") in wallet_addresses)
        for i in t.get("vin", []):
            prev = i.get("prevout") or {}
            if prev.get("scriptpubkey_address") in wallet_addresses:
                sats -= prev.get("value", 0)
        status = t.get("status") or {}
        confirmed = bool(status.get("confirmed"))
        rows.append({"sats": sats, "time": status.get("block_time") if confirmed else None, "confirmed": confirmed})
    rows.sort(key=lambda r: (r["confirmed"], -(r["time"] or 0)))
    return rows[:limit]


def scan(xpub, fetch_json, gap_limit=20, max_txs=10):
    """Scans the receive (0) and change (1) chains. fetch_json(path) reads a path below API_BASE."""
    key = _account_key(xpub)
    used = {}
    for chain in (0, 1):
        index, gap = 0, 0
        while gap < gap_limit:
            address = derive_address(None, chain, index, _key=key)
            stats = fetch_json("/address/%s" % address)
            if _tx_count(stats) > 0:
                used[address] = stats
                gap = 0
            else:
                gap += 1
            index += 1

    txs = []
    for address in used:
        txs.extend(fetch_json("/address/%s/txs" % address))
    all_rows = net_txs(txs, set(used), limit=len(txs) or 1)

    return {
        "balance_sats": sum(_sum(s, "chain_stats") + _sum(s, "mempool_stats") for s in used.values()),
        "pending_sats": sum(_sum(s, "mempool_stats") for s in used.values()),
        "tx_count": len({t["txid"] for t in txs}),
        "addresses_used": len(used),
        "txs": all_rows[:max_txs],
        "updated": int(time.time()),
    }


# ---------- cache ----------
class Wallet:
    def __init__(self, xpub, fetch_json, cache_seconds=300, gap_limit=20, max_txs=10, clock=time.time):
        self.xpub, self.fetch_json, self.clock = xpub, fetch_json, clock
        self.cache_seconds, self.gap_limit, self.max_txs = cache_seconds, gap_limit, max_txs
        self.body, self.at = None, None
        self.lock = threading.Lock()

    def get(self):
        with self.lock:
            if self.body is not None and self.clock() - self.at < self.cache_seconds:
                return 200, self.body
            try:
                self.body = scan(self.xpub, self.fetch_json, self.gap_limit, self.max_txs)
                self.at = self.clock()
                return 200, self.body
            except ValueError as error:
                return 502, {"error": str(error)}
            except Exception as error:
                log.warning("Scan failed: %s", type(error).__name__)
                if self.body is not None:
                    return 200, self.body
                return 502, {"error": "Could not read the wallet from the mempool API."}


def http_fetcher(api_base, timeout=15):
    def fetch_json(path):
        request = urllib.request.Request(api_base.rstrip("/") + path, headers={"User-Agent": "bitcoin-trmnl-sidecar"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    return fetch_json


def make_handler(wallet):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0].rstrip("/")
            if path == "/wallet":
                status, body = wallet.get()
            elif path == "/health":
                status, body = 200, {"ok": True}
            else:
                status, body = 404, {"error": "Not found."}
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):
            log.info("%s %s", self.command, self.path.split("?")[0])

    return Handler


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    xpub = os.environ.get("XPUB", "")
    try:
        _account_key(xpub)
        log.info("Account key loaded.")
    except ValueError as error:
        log.error("%s /wallet will answer 502 until this is fixed.", error)
    from embit.util import secp256k1
    log.info("secp256k1 backend: %s", getattr(secp256k1, "__name__", "?"))

    wallet = Wallet(
        xpub,
        http_fetcher(os.environ.get("API_BASE", "https://mempool.space/api")),
        cache_seconds=int(os.environ.get("CACHE_SECONDS", "300")),
        gap_limit=int(os.environ.get("GAP_LIMIT", "20")),
        max_txs=int(os.environ.get("MAX_TXS", "10")),
    )
    port = int(os.environ.get("PORT", "8091"))
    log.info("Listening on port %d.", port)
    ThreadingHTTPServer(("0.0.0.0", port), make_handler(wallet)).serve_forever()


if __name__ == "__main__":
    main()
