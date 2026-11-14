# Bitcoin wallet for Terminus

This repo holds a [Terminus](https://github.com/usetrmnl/terminus) extension that shows a Bitcoin wallet on an e-ink screen.
It watches one public address, or a whole wallet through a small helper service, and adds general Bitcoin network stats.
All data comes from [mempool.space](https://mempool.space/docs/api) and [CoinGecko](https://www.coingecko.com/en/api), which are free and need no API key.

The extension only reads public data. It never asks for a private key or a seed phrase, and it cannot move coins.

Wallets like Ledger Live give you a new receive address for every payment, so one address shows only part of your coins, often none.
To see the whole wallet, run the helper service in `service/`. See [Whole wallet (xpub)](#whole-wallet-xpub).

The two extension files use Terminus's own export format, so Terminus can import them directly.

| File | Contents |
| --- | --- |
| `configuration.yml` | The extension settings, its form fields, the default data and the exchange. |
| `template.html.liquid` | The Liquid template. |

The `service/` folder holds the optional wallet service. The `test/` folder, `package.json` and `docs/` are for development. Do not upload any of them to Terminus.

## What the screen shows

- The balance of the address in BTC or sats, and its value in your currency. Unconfirmed incoming coins count in the balance.
- The current Bitcoin price and its change over 7 and 30 days.
- A chart of the price over the last 30 days, with the high and low.
- The two most recent transactions on the address, with the net amount and the date. An unconfirmed transaction shows "Pending".
- Six network stats:
  - recommended fees for fast, 30-minute and 1-hour confirmation, in sat/vB
  - the current block height
  - blocks left until the next halving, with an estimated month
  - the expected change at the next difficulty adjustment, and the days left
  - the network hashrate
  - the number of unconfirmed transactions in the mempool

When a data source fails, its section shows "—" and the rest of the screen still renders.
The title bar shows the shortened address and the time of the last price update, so you can see when the data is stale.

The layout adapts to the screen shape. In portrait the template stacks the sections and shows the stats in two columns.

## How it works

Terminus fetches the data through one exchange with eight addresses.
Each response becomes a source that the template reads, in this order:

| Source | Address | Used for |
| --- | --- | --- |
| `source_1` | `{api_base}/address/{address}` | Balance |
| `source_2` | `{api_base}/address/{address}/txs` | Recent transactions |
| `source_3` | `{api_base}/v1/prices` | Current price and update time |
| `source_4` | `{api_base}/v1/difficulty-adjustment` | Difficulty change, block height and halving estimate |
| `source_5` | `{api_base}/v1/mining/hashrate/3d` | Hashrate |
| `source_6` | `{api_base}/v1/fees/recommended` | Fees |
| `source_7` | `{api_base}/mempool` | Mempool size |
| `source_8` | CoinGecko `coins/bitcoin/market_chart`, 30 days, daily | Chart and price changes |

When one request fails, Terminus keeps that source's previous data.
A script at the bottom of the template draws the screen in the browser that renders it.

## Set it up

1. Zip the two files. The zip must hold them at its top level, not inside a folder:

   ```bash
   zip extension.zip configuration.yml template.html.liquid
   ```

2. In Terminus, open **Extensions**, click **Upload**, and attach `extension.zip`. Terminus creates the extension with its fields, data and exchange.
3. Open the new extension. Under **Data**, set `address` to your public Bitcoin address. The default is the genesis block address, which is only a placeholder.
4. Under **Build Matrix**, choose **Models** and select your device's model. The export format does not include this setting.
5. Save the extension, then click **Build**. Terminus renders a screen for each selected model.
6. Open your device's playlist and add the new screen.

## Whole wallet (xpub)

The wallet service reads your account's extended public key (xpub), finds every address the account has used, and adds up the balance.
It also nets each transaction against the whole wallet, so change sent back to your own addresses does not show as income.
It supports one native SegWit account (`bc1q…` addresses), which is the Ledger Live default.

An xpub cannot spend coins. It does reveal every address and transaction in the wallet, so treat it as private: keep it out of git, chats and screenshots.
The service never logs it and never returns it.

### Find your xpub in Ledger Live

1. Open the account, for example **Bitcoin 1**.
2. Click the wrench icon, then **Advanced**.
3. Copy the value that starts with `xpub`.

### Run the service on Portainer

1. In Portainer, open **Stacks** and click **Add stack**.
2. Choose **Repository**. Use `https://github.com/kmgalanakis/bitcoin-trmnl` as the repository URL and `service/compose.portainer.yaml` as the compose path.
3. Under **Environment variables**, add `XPUB` with your xpub. The other settings in `service/.env.example` have defaults.
4. Deploy the stack. Portainer builds the image from the repo and starts `bitcoin-wallet-sidecar` on port 8091.
5. Open `http://<server>:8091/wallet` in a browser. The first scan takes about half a minute. Until it finishes, the page answers with an error that says so.

The service scans in the background every 10 minutes and spaces its requests, because mempool.space refuses requests that come too fast.
`/wallet` always answers at once with the latest finished scan. When a scan fails, the last good scan stays in place.

The image deletes embit's bundled compiled libraries, so the service runs pure Python. It works on CPUs without x86-64-v2.

### Point the extension at the service

In Terminus, open the extension. Under **Data**, set `wallet_url` to the service address, for example `http://192.168.1.152:8091/wallet`, then save and build.
The screen then shows the whole wallet, and the title bar shows how many addresses the wallet has used.
To go back to one address, set `wallet_url` to an empty string.

## Settings

| Field | Default | Meaning |
| --- | --- | --- |
| `address` | the genesis block address | The public address to watch. |
| `label` | `Bitcoin` | Name shown in the title bar. |
| `currency` | `EUR` | `EUR`, `USD`, `GBP`, `CAD`, `CHF`, `AUD` or `JPY`. |
| `unit` | `BTC` | `BTC` or `sats`. |
| `locale` | `en-GB` | Language for numbers and dates, such as `el-GR`. |
| `timezone` | `Europe/Athens` | Time zone for dates and the update time. |
| `api_base` | `https://mempool.space/api` | The mempool API to use. |
| `wallet_url` | empty | The wallet service's `/wallet` address. When set, it replaces `address`. |

## Privacy

mempool.space sees which address your server asks about, and from which IP address.
In wallet mode it sees all your addresses asked about from one IP address, so it can link them.
To keep the addresses private, run your own [mempool](https://github.com/mempool/mempool) server. Set `api_base` in the extension and `API_BASE` in the service to its API, for example `http://umbrel.local:3006/api`.
The CoinGecko request does not include your address.

## Develop

The tests load the script from the template and check the data functions and the screen markup:

```bash
npm install
npm test
```

`npm run render` fills the template with the saved responses in `test/fixtures/` and saves screenshots in `test/out/`.
Set `SCENARIO=empty` to render the screen with no data, or `SCENARIO=wallet` for wallet mode.

The wallet service has its own tests. They use the public BIP84 test vector key, never a real xpub:

```bash
python3 -m venv service/.venv
service/.venv/bin/pip install -r service/requirements.txt
service/.venv/bin/python -m unittest -v service/test_app.py
```
If Playwright reports a missing browser, run `npx playwright install chromium`, or point `CHROMIUM` at a Chromium you already have.

## Keep the copies in sync

Terminus stores the live copy of the extension.
When you change the extension in Terminus, click its **Download** link on the **Extensions** page and unzip the export over the two files.
The export saves the template with Windows line endings. Convert it to Unix line endings before you commit:

```bash
tr -d '\r' < template.html.liquid > t && mv t template.html.liquid
```

## License

MIT. See [LICENSE](LICENSE).
