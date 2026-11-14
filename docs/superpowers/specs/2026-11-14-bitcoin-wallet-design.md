# Bitcoin wallet extension for Terminus: design

Approved by the owner on 2026-11-14.

## Intent

The owner runs a self-hosted Terminus server for TRMNL-style e-ink screens. TRMNL's official Bitcoin Wallet plugin is a native plugin, and Terminus does not support native plugins yet. No community recipe shows a wallet balance. This extension fills that gap. It shows the balance of one public Bitcoin address, plus general Bitcoin network stats.

## Goals

- Show the balance of one address in BTC or sats, and its value in a chosen currency.
- Show the current price, the 7-day and 30-day change, and a 30-day price chart.
- Show the two most recent transactions on the address, with their confirmation state.
- Show six network stats: recommended fees, block height, halving countdown, next difficulty change, hashrate, and mempool size.
- Work in landscape and portrait, like the owner's weather extension.

## Non-goals

- No xpub or multi-address wallets. That needs a helper service and is a later step.
- No private keys, signing or sending. The extension only reads public data.
- No market cap or other market stats beyond the price.

## Anti-goals

- Never ask for or store anything secret. The address is the only input.
- Never show a broken layout. When data is missing, show a clear message or hide that section.

## Constraints

- It uses Terminus's export format: `configuration.yml` and `template.html.liquid`, zipped and uploaded. This is the same format as `weather-trmnl`, `gcal-dayview-trmnl` and `freedom24-trmnl`.
- Terminus renders screens in Chromium, so the template can draw the screen with a script. The weather extension does the same.
- One exchange holds several addresses separated by spaces. Terminus stores each response as `source_1`, `source_2` and so on, in order. When one request fails, Terminus keeps that source's previous data and records an error.
- Every data source must be free and need no API key.

## Approaches

1. **Poll extension with public APIs (chosen).** Terminus fetches the data, and the template draws it. It needs no extra service, and it matches the owner's other extensions.
2. **Helper service, like `freedom24-trmnl`.** This is only needed for xpub support. It adds a container to run, for no gain with one address.
3. **TRMNL recipe or native plugin.** Terminus cannot run native plugins. A recipe would still need its own data source, so it gains nothing over approach 1.

## Data sources

All mempool.space paths are relative to the `api_base` field, which defaults to `https://mempool.space/api`. The owner can point it at a self-hosted mempool server later.

| Source | Request | Used for |
| --- | --- | --- |
| `source_1` | `{api_base}/address/{address}` | Balance from `chain_stats` and `mempool_stats` (funded minus spent), and the transaction count |
| `source_2` | `{api_base}/address/{address}/txs` | The two most recent transactions: net change for this address, date, confirmed or not |
| `source_3` | `{api_base}/v1/prices` | Current price in the chosen currency |
| `source_4` | `{api_base}/v1/difficulty-adjustment` | Difficulty change and time left. The block height is `nextRetargetHeight - remainingBlocks`. |
| `source_5` | `{api_base}/v1/mining/hashrate/3d` | `currentHashrate` |
| `source_6` | `{api_base}/v1/fees/recommended` | Fast, 30-minute and 1-hour fee rates |
| `source_7` | `{api_base}/mempool` | Unconfirmed transaction count |
| `source_8` | CoinGecko `coins/bitcoin/market_chart?vs_currency={currency}&days=30&interval=daily` | The 30-day chart and the 7-day and 30-day change |

Notes from testing on 2026-11-14:

- `/blocks/tip/height` returns plain text, so the template calculates the height from `source_4` instead.
- mempool.space's full price history is 1.5 MB, which is too large. CoinGecko's daily series is 3 KB.
- `v1/prices` supports USD, EUR, GBP, CAD, CHF, AUD and JPY. The currency field offers these.
- The halving countdown uses the next multiple of 210,000 blocks above the current height. The estimated date uses `timeAvg` from `source_4`.

## Fields

| Key | Default | Meaning |
| --- | --- | --- |
| `address` | a well-known public address, as a placeholder | The address to watch |
| `label` | `Bitcoin` | Wallet name in the title bar |
| `currency` | `EUR` | One of the `v1/prices` currencies |
| `unit` | `BTC` | `BTC` or `sats` |
| `locale` | `en-GB` | Number and date formatting |
| `api_base` | `https://mempool.space/api` | mempool API root |
| `timezone` | `Europe/Athens` | Time zone for dates and the update time. Added during the build. |

The refresh interval is 15 minutes, like the weather extension.

## Screen

Landscape, 800×480:

```
┌ Cold storage ───────────────────── bc1q…x7f3 ┐
│  0.48213 BTC   € 41,902    BTC € 86,910 +4.2% │
│ ─────────────────────────────────────────────│
│ FEES      BLOCK     HALVING   DIFFICULTY      │
│ 12/8/5    921,034   128k blk  +2.1% in 6d     │
│ HASHRATE  MEMPOOL                             │
│ 1.1 EH/s  42k tx                              │
│ ╭─ 30-day price ───────╮  +0.05 BTC 12 Nov ✓  │
│ ╰──────────────────────╯  −0.01 BTC 02 Nov    │
└───────────────────────────────────────────────┘
```

Portrait stacks the hero, the stats grid as two columns, the chart, and the transactions.

## Failure behaviour

- If address data is missing, the hero shows "Address unavailable" and the network stats still render.
- If the chart data is missing, the chart area shows the price change from `v1/prices` alone and hides the chart.
- Any missing stat shows "—".
- The title bar shows when the price data was last updated, so stale data is visible.

## Left to the builder

- Exact typography and spacing, within the style of the weather extension.
- How the address is shortened in the title bar.
- How a transaction's net change is calculated: outputs to the address minus inputs from it.
