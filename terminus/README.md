# Terminus extension

This folder holds the Terminus extension that shows a Bitcoin wallet and network stats on an e-ink screen.
The two extension files use the format that Terminus itself exports and imports.

| File | Contents |
| --- | --- |
| `configuration.yml` | The extension settings, its form fields, the default data and the exchange. |
| `template.html.liquid` | The Liquid template that renders the screen. |

The `test/` folder and `package.json` are for development. Do not upload them.

The extension works in two modes:

- **Single address.** Terminus reads one public address straight from mempool.space. You don't need the sidecar.
- **Whole wallet.** Terminus reads the sidecar's `/wallet` JSON, which covers every address in the account. See the main [README](../README.md) to run the sidecar.

## What the screen shows

- The balance in BTC or sats, and its value in your currency. Unconfirmed incoming coins count in the balance.
- The current Bitcoin price and its change over 7 and 30 days.
- A chart of the price over the last 30 days, with the high and low.
- The two most recent transactions, with the net amount and the date. An unconfirmed transaction shows "Pending".
- Six network stats:
  - recommended fees for fast, 30-minute and 1-hour confirmation, in sat/vB
  - the current block height
  - blocks left until the next halving, with an estimated month
  - the expected change at the next difficulty adjustment, and the days left
  - the network hashrate
  - the number of unconfirmed transactions in the mempool

When a data source fails, its section shows "—" and the rest of the screen still renders.
The title bar shows the shortened address, or how many addresses the wallet has used in wallet mode. It also shows the time of the last price update, so you can see when the data is stale.

The layout adapts to the screen shape. In portrait the template stacks the sections and shows the stats in two columns.

## How it works

Terminus fetches the data through one exchange with eight addresses.
Each response becomes a source that the template reads, in this order:

| Source | Address | Used for |
| --- | --- | --- |
| `source_1` | `{api_base}/address/{address}`, or `wallet_url` | Balance |
| `source_2` | `{api_base}/address/{address}/txs`, or `wallet_url` | Recent transactions |
| `source_3` | `{api_base}/v1/prices` | Current price and update time |
| `source_4` | `{api_base}/v1/difficulty-adjustment` | Difficulty change, block height and halving estimate |
| `source_5` | `{api_base}/v1/mining/hashrate/3d` | Hashrate |
| `source_6` | `{api_base}/v1/fees/recommended` | Fees |
| `source_7` | `{api_base}/mempool` | Mempool size |
| `source_8` | CoinGecko `coins/bitcoin/market_chart`, 30 days, daily | Chart and price changes |

When `wallet_url` is set, the first two sources both read it. The template recognises the sidecar's JSON by its `balance_sats` key.
When one request fails, Terminus keeps that source's previous data.
A script at the bottom of the template draws the screen in the browser that renders it.

## Set it up

1. Zip the two files. The zip must hold them at its top level, not inside a folder:

   ```bash
   cd terminus && zip ../extension.zip configuration.yml template.html.liquid
   ```

2. In Terminus, open **Extensions**, click **Upload**, and attach `extension.zip`. Terminus creates the extension with its fields, data and exchange.
3. Open the new extension. Under **Data**, set one of these:
   - `wallet_url` to the sidecar's address, for example `http://192.168.1.152:8091/wallet`.
     Do not use `localhost`. Terminus runs in its own container, so `localhost` points at Terminus itself.
   - or `address` to one public Bitcoin address. The default is the genesis block address, which is only a placeholder.
4. Under **Build Matrix**, choose **Models** and select your device's model. The export format does not include this setting.
5. Save the extension, then click **Build**. Terminus renders a screen for each selected model.
6. Open your device's playlist and add the new screen.

## Settings

| Field | Default | Meaning |
| --- | --- | --- |
| `wallet_url` | empty | The sidecar's `/wallet` address. When set, it replaces `address`. |
| `address` | the genesis block address | The public address to watch in single-address mode. |
| `label` | `Bitcoin` | Name shown in the title bar. |
| `currency` | `USD` | `USD`, `EUR`, `GBP`, `CAD`, `CHF`, `AUD` or `JPY`. Sets the currency for the balance value, the price and the chart. |
| `unit` | `BTC` | `BTC` or `sats`. |
| `locale` | `en-GB` | Language for numbers and dates, such as `el-GR`. |
| `timezone` | `Europe/Athens` | Time zone for dates and the update time. |
| `api_base` | `https://mempool.space/api` | The mempool API to use. |

## Privacy

In single-address mode, mempool.space sees which address your server asks about, and from which IP address.
To keep it private, run your own [mempool](https://github.com/mempool/mempool) server and set `api_base` to its API, for example `http://umbrel.local:3006/api`.
The CoinGecko request does not include your address.

## Develop

The tests load the script from the template and check the data functions and the screen markup:

```bash
cd terminus
npm install
npm test
```

`npm run render` fills the template with the saved responses in `test/fixtures/` and saves screenshots in `test/out/`.
Set `SCENARIO=empty` to render the screen with no data, or `SCENARIO=wallet` for wallet mode.
If Playwright reports a missing browser, run `npx playwright install chromium`, or point `CHROMIUM` at a Chromium you already have.

## Keep the copies in sync

Terminus stores the live copy of the extension.
When you change the extension in Terminus, click its **Download** link on the **Extensions** page and unzip the export over the two files.
The export saves the template with Windows line endings. Convert it to Unix line endings before you commit:

```bash
tr -d '\r' < template.html.liquid > t && mv t template.html.liquid
```
