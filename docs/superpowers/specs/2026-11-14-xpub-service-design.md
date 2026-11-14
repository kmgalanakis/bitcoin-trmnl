# Wallet (xpub) mode: design

Approved by the owner on 2026-11-14.

## Intent

The owner's coins are in a Ledger Live account called "Bitcoin 1", which is Native SegWit. Ledger Live shows a fresh unused receive address for each payment, so the coins are spread over many addresses. The single-address extension showed 0 for that reason. Wallet mode shows the whole account balance and its transactions, using the account's extended public key (xpub).

## Goals

- Show the total balance of one native SegWit account from its xpub, including unconfirmed coins.
- Show the account's recent transactions. A transaction's amount is its net effect on the whole wallet, so change sent back to the wallet does not count as income.
- Keep single-address mode working, along with the network stats, the chart and the layout.

## Non-goals

- Several accounts, or Taproot, nested SegWit or legacy accounts. The address-type choice sits in one function, so adding a type later is a small change.
- Spending, signing, or anything that needs a private key.

## Anti-goals

- The xpub never appears in git, in Terminus, in logs, or in any HTTP response. An xpub cannot spend coins, but it reveals every address and transaction in the wallet.
- The service never runs compiled code. The Portainer server's CPU lacks x86-64-v2.

## Constraints

- The service follows `freedom24-trmnl`: one stdlib-HTTP `app.py`, a `python:3.12-alpine` image, a Portainer stack built from git with `pull_policy: build` and `env_file: stack.env`, and LAN-only port publishing.
- Address derivation uses `embit==0.8.0`, a pure-Python library. The Dockerfile deletes `embit/util/prebuilt`, so embit falls back to its pure-Python secp256k1.
- Data comes from the mempool.space REST API, configurable through `API_BASE`.

## Approaches

1. **Helper service in `bitcoin-trmnl/service/` (chosen).** The xpub stays in Portainer, and the address scan and transaction netting happen in tested Python.
2. **blockchain.info `multiaddr` with the xpub, polled by Terminus directly.** Rejected. Testing showed it derives legacy addresses from a native SegWit xpub: it found 2 transactions where the BIP84 test wallet's first address has 180. It would also expose the xpub in Terminus and send the wallet history to a third party.
3. **List the derived addresses in the Terminus exchange.** Rejected. The list goes stale as soon as Ledger uses a new address, and netting is not possible in Liquid.

## Service

Environment, documented in `service/.env.example`:

| Variable | Default | Meaning |
| --- | --- | --- |
| `XPUB` | (required) | The account's xpub from Ledger Live. zpub also works. |
| `API_BASE` | `https://mempool.space/api` | The mempool REST API. |
| `GAP_LIMIT` | `20` | Stop each chain after this many unused addresses in a row. |
| `CACHE_SECONDS` | `300` | How long to reuse the last scan. |
| `MAX_TXS` | `10` | Transactions in the response. |
| `PORT` | `8091` | HTTP port. |

Scan: for the receive chain (0) and the change chain (1), derive `m/<chain>/<i>` from the account xpub as P2WPKH. For each address, read `{API_BASE}/address/<a>`. An address is used when its chain or mempool `tx_count` is above 0. Stop after `GAP_LIMIT` unused addresses in a row. For each used address, read `{API_BASE}/address/<a>/txs`. Merge the results by txid.

`GET /wallet` returns:

```json
{"balance_sats": 0, "pending_sats": 0, "tx_count": 0, "addresses_used": 0,
 "txs": [{"sats": 0, "time": 0, "confirmed": true}], "updated": 0}
```

- `balance_sats` is confirmed plus mempool funds. `pending_sats` is the mempool part alone.
- In `txs`, unconfirmed transactions come first, then confirmed ones by `block_time`, newest first. `time` is null when unconfirmed.
- If a scan fails and a cached scan exists, the service returns the cached scan. Otherwise it returns HTTP 502 with `{"error": "..."}`, and Terminus keeps that source's previous data.
- `GET /health` returns `{"ok": true}`. No other path exposes data.

## Extension changes

- There is a new field, `wallet_url`, empty by default. When it is set, the exchange's first two addresses are both `wallet_url`, through a Liquid `if` in the exchange template. Otherwise they are the address URLs, as before. Sources 3 to 8 do not change.
- The template detects wallet data by the `balance_sats` key on `source_1`. In that case it takes the balance and transactions from it. In single-address mode the template keeps its current behaviour.
- In wallet mode the title bar shows "N addresses" instead of the shortened address.

## Left to the builder

- The HTTP handler's structure, logging format, and the timeout for each request.
- Whether mempool requests run one after another or a few at a time, within mempool.space's rate limits.
