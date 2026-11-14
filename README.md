# Bitcoin wallet → TRMNL Terminus sidecar

This repo shows a Bitcoin wallet on an e-ink screen through [Terminus](https://github.com/usetrmnl/terminus). It has two parts:

- **The sidecar** (`app.py`) reads your wallet's extended public key (xpub), finds every address the wallet has used, and serves the total balance and recent transactions as JSON.
- **The Terminus extension** (`terminus/`) renders that JSON as a screen, with the price, a 30-day chart and six Bitcoin network stats.

Wallets like Ledger Live give you a new receive address for every payment, so one address shows only part of your coins, often none. The sidecar solves that.
If you only want to watch one address, you can skip the sidecar. The extension can read a single address straight from mempool.space.

Everything is read-only. The sidecar and the extension never ask for a private key or a seed phrase, and they cannot move coins.

## Contents

| File | Purpose |
| --- | --- |
| `app.py` | The sidecar: address scan, transaction netting and the HTTP server |
| `test_app.py` | Tests for the sidecar |
| `requirements.txt` | Python dependencies: `embit`, pure Python |
| `Dockerfile` | Image build |
| `compose.yaml` | Docker Compose setup for a local run |
| `compose.portainer.yaml` | Docker Compose setup for a Portainer stack |
| `.env.example` | Template for your settings |
| `terminus/` | The Terminus extension: template, settings and setup steps |
| `docs/` | Design notes and plans |

## Requirements

- Docker, or Python 3.9 or newer.
- A Bitcoin account with native SegWit addresses (`bc1q…`). This is the Ledger Live default.
- A Terminus server on the same network.

## 1. Find your xpub

In Ledger Live:

1. Open the account, for example **Bitcoin 1**.
2. Click the wrench icon, then **Advanced**.
3. Copy the value that starts with `xpub`.

An xpub cannot spend coins. It does reveal every address and transaction in the wallet, so treat it as private: keep it out of git, chats and screenshots.
The sidecar never logs it and never returns it.

## 2. Configure

Copy `.env.example` to `.env` and set `XPUB`:

```bash
cp .env.example .env
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `XPUB` | (required) | The account's xpub. A zpub also works. |
| `API_BASE` | `https://mempool.space/api` | The mempool REST API. |
| `GAP_LIMIT` | `20` | Stop each address chain after this many unused addresses in a row. |
| `SCAN_SECONDS` | `600` | Seconds between background scans. |
| `REQUEST_DELAY` | `0.5` | Seconds between API requests. |
| `MAX_TXS` | `10` | Transactions in the response. |
| `PORT` | `8091` | HTTP port. |

`.env` is in `.gitignore`. Never commit it.

## 3. Run the sidecar

### With Docker Compose

```bash
docker compose up -d --build
```

The first scan takes about half a minute. Then check the result:

```bash
curl http://localhost:8091/wallet
```

### Without Docker

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
set -a && . ./.env && set +a && .venv/bin/python app.py
```

## 4. Add the Terminus extension

Follow [terminus/README.md](terminus/README.md).

## Deploy with Portainer

1. In Portainer, open **Stacks** and click **Add stack**.
2. Choose **Repository**. Use `https://github.com/kmgalanakis/bitcoin-trmnl` as the repository URL and `compose.portainer.yaml` as the compose path.
3. Under **Environment variables**, add `XPUB` with your xpub. The other settings have defaults.
4. Deploy the stack. Portainer builds the image from the repo and starts `bitcoin-wallet-sidecar` on port 8091.

Portainer writes the stack's variables to `stack.env` at the root of its repo checkout. That is why `compose.portainer.yaml` stays at the repo root.
The service has no image name, and `pull_policy: build` makes Portainer build from the repo on every deploy. With an image name, Portainer's **Re-pull image** would try to pull it from Docker Hub and fail.

## API

### `GET /wallet`

```json
{
  "balance_sats": 123456789,
  "pending_sats": 50000,
  "tx_count": 5,
  "addresses_used": 7,
  "txs": [
    {"sats": 50000, "time": null, "confirmed": false},
    {"sats": -31000, "time": 1794000000, "confirmed": true}
  ],
  "updated": 1794650000
}
```

- `balance_sats` holds confirmed plus unconfirmed funds. `pending_sats` is the unconfirmed part alone.
- Each row in `txs` is the transaction's net effect on the whole wallet, in sats. Unconfirmed transactions come first, then the rest, newest first.
- Before the first scan finishes, or when the xpub is missing or invalid, the answer is HTTP 502 with `{"error": "..."}`.

### `GET /health`

Returns `{"ok": true}`.

## How it works

1. The sidecar derives the account's native SegWit addresses on the receive chain (`0/i`) and the change chain (`1/i`).
2. It asks mempool.space about each address and stops a chain after 20 unused addresses in a row. Ledger uses the same gap limit.
3. For each used address it reads the recent transactions and merges them by transaction ID.
4. It nets each transaction against all wallet addresses. Change sent back to the wallet therefore does not count as income, and a transfer between your own addresses shows only the fee.

The sidecar scans in a background thread every 10 minutes, so `/wallet` answers at once with the latest finished scan.
It waits half a second between requests and retries a "429 Too Many Requests" answer after 5, 10, 20 and 40 seconds, because mempool.space refuses requests that come too fast.
When a scan fails, the last good scan stays in place.

The image deletes embit's bundled compiled libraries, so the sidecar runs pure Python. It works on CPUs without x86-64-v2.

## Tests

The tests use the public BIP84 test vector key, never a real xpub:

```bash
.venv/bin/python -m unittest -v test_app.py
```

The extension has its own tests. See [terminus/README.md](terminus/README.md#develop).

## Security

- The sidecar has no login. Publish port 8091 on your LAN only, and never port-forward it on your router.
- The xpub lives only in `.env` or in Portainer's stack settings.
- mempool.space sees all your addresses asked about from one IP address, so it can link them. To avoid that, run your own [mempool](https://github.com/mempool/mempool) server and set `API_BASE` to its API, for example `http://umbrel.local:3006/api`.

## License

MIT. See [LICENSE](LICENSE).
