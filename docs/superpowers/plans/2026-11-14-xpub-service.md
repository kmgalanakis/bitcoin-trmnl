# Wallet (xpub) Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a LAN helper service that turns a Ledger xpub into a wallet balance and transactions, and teach the extension to show it.

**Architecture:** `service/app.py` is a stdlib HTTP server. Its pure functions handle derivation, the scan and the netting, and the network calls go through one injectable `fetch_json(url)`. The extension gains a `wallet_url` field and a wallet branch in `render`.

**Tech Stack:** Python 3.12 (alpine), `embit==0.8.0` pure Python, `unittest`, plus the extension's existing Node tests.

**Spec:** `docs/superpowers/specs/2026-11-14-xpub-service-design.md`

## Global Constraints

- The xpub must never appear in output, logs or the repo. Tests use the public BIP84 test vector zpub only.
- No compiled code at runtime: the Dockerfile removes `embit/util/prebuilt`.
- The port is 8091, the gap limit is 20, the cache lasts 300 s, and the response holds at most 10 txs.

## Review Focus

- A wallet whose used addresses have gaps shorter than 20: the scan must keep going past them. Test in Task 1.
- A transaction between two of the wallet's own addresses (self-transfer): the net is minus the fee only. Test in Task 1.
- The same tx seen from two addresses: it is counted once. Test in Task 1.
- The mempool API fails mid-scan: the service returns the cached scan if there is one, otherwise 502. It never returns a partial balance. Test in Task 1.
- An empty or invalid `XPUB`: the service starts, logs a clear error without the value, and `/wallet` returns 502. Test in Task 1.

---

### Task 1: Service core with tests

**Files:** Create `service/app.py` and `service/test_app.py`. Tests run with `service/.venv/bin/python -m unittest -v service/test_app.py`, where the venv has embit 0.8.0 installed. In the image, Python 3.12 runs the same code.

**Interfaces (Produces):**
- `derive_address(xpub: str, chain: int, index: int) -> str`: P2WPKH mainnet address.
- `scan(xpub, fetch_json, gap_limit=20) -> dict`: the `/wallet` response shape from the spec. `fetch_json(path)` takes a path relative to `API_BASE` and returns parsed JSON or raises.
- `net_txs(txs: list, wallet_addresses: set, limit: int) -> list[dict]`
- `class Wallet` with `get() -> (status: int, body: dict)`. It applies the cache and the stale-on-error rule.

- [ ] Tests: `derive_address(BIP84_ZPUB, 0, 0) == 'bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu'`, `(0, 1) == 'bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g'`, and `(1, 0) == 'bc1q8c6fshw2dlwun7ekn9qwf37cu2rn755upcp6el'`.
- [ ] Tests for `scan`, using a fake `fetch_json` keyed by address: used addresses at receive 0, 3 and 15, and change 0, with gap limit 20. The test checks that all four are found and that the sums are right. Another test checks that a self-transfer nets to minus the fee, and that a duplicate txid appears once. Another checks the ordering: unconfirmed first, then newest first.
- [ ] Tests for `Wallet`: a fetch that fails on the first call returns 502. After one successful scan, a failing rescan returns 200 with the cached body. An invalid XPUB returns 502, and the error text does not contain the xpub.
- [ ] Watch the tests fail, implement, then watch them pass. Commit with "Add the xpub wallet service".

### Task 2: Container and stack

**Files:** Create `service/Dockerfile`, `service/requirements.txt` (`embit==0.8.0`), `compose.portainer.yaml` at the repo root, since Portainer writes `stack.env` there (container `bitcoin-wallet-sidecar`, `ports: "8091:8091"`) and `service/.env.example`.

- [ ] Build with `docker build --platform linux/amd64 -t btc-wallet-test service/`. Then run the tests and a backend check inside it. Expected: the tests pass, and `embit.util.secp256k1` reports the pure-Python module (`py_secp256k1`).
- [ ] Run the container with the BIP84 zpub and call `curl localhost:8091/wallet`. Expected: JSON with `addresses_used` above 0, and no zpub in the body. Commit with "Add the Docker setup for the wallet service".

### Task 3: Extension wallet mode

**Files:** Modify `template.html.liquid`, `configuration.yml` and `test/btc.test.js`. Add `test/fixtures/wallet.json`.

- [ ] Tests: `balanceSats(wallet)` returns `wallet.balance_sats`. `render` with `addr: wallet, txs: wallet` shows the wallet balance, the wallet's tx rows, and "N addresses" as the returned `address`. Single-address tests stay green.
- [ ] Implement it. Add the `wallet_url` field and the Liquid `if` in the exchange. Check the exchange in both modes with the ruby expansion check, adapted for the `if`. Re-render the screenshots. Commit with "Show a whole wallet from the xpub service".

### Task 4: README

- [ ] Add a "Whole wallet (xpub)" section to the README. It covers what the xpub is and how to find it in Ledger Live, the Portainer stack steps (repo URL, compose path `service/compose.portainer.yaml`, the `XPUB` variable), setting `wallet_url` in Terminus, and the privacy note. Commit with "Document wallet mode".
