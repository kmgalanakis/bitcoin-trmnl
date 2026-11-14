# Bitcoin Wallet Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Terminus Poll extension that shows one Bitcoin address's balance, the price, a 30-day chart, recent transactions and six network stats.

**Architecture:** `configuration.yml` defines the fields and one exchange with eight addresses, which become `source_1` to `source_8`. `template.html.liquid` passes each source into the page as JSON. A script inside `{% raw %}` defines `BTC`, a module with pure data functions and a `render` function. The script ends with `module.exports = BTC` so Node tests can load it, as in `weather-trmnl`.

**Tech Stack:** Liquid (Terminus/Superfluid), plain browser JavaScript, the TRMNL framework CSS, Node 20+ `node:test` for tests, and liquidjs plus Playwright for the local render harness. The test tools live under `test/` and are never uploaded.

**Spec:** `docs/superpowers/specs/2026-11-14-bitcoin-wallet-design.md`

## Global Constraints

- Export format: the same keys as `../weather-trmnl/configuration.yml`, with `kind: poll`, `mode: text`, `interval: 15`, `unit: minute`.
- Exchange order is fixed: address, txs, prices, difficulty-adjustment, hashrate/3d, fees/recommended, mempool, CoinGecko market_chart.
- Fields: `address`, `label` (default `Bitcoin`), `currency` (`EUR` default; USD, EUR, GBP, CAD, CHF, AUD, JPY), `unit` (`BTC` or `sats`), `locale` (`en-GB`), `api_base` (`https://mempool.space/api`).
- No API keys. No secrets in any file.
- Halving interval is 210,000 blocks. 1 BTC is 100,000,000 sats.
- Any missing value renders as `—`. A missing source never throws out of `render`.

## Review Focus

- A brand-new address with zero transactions: the balance shows 0 and the transactions area shows "No transactions yet". Test in Task 1.
- An unconfirmed incoming transaction: it counts in the balance through `mempool_stats` and shows as pending. Test in Task 1.
- A transaction that both spends from and pays back to the address (change): the net value is outputs minus inputs, not the gross amount. Test in Task 1.
- A source that holds an error object or `null` because the first fetch failed: that section shows `—` and the other sections still render. Test in Task 1.
- Very large or very small values, such as 0.00001 BTC or 2,000 BTC in sats: the numbers stay on one line and are formatted with thousands separators. Test in Task 1.

---

### Task 1: Data functions with tests

**Files:**
- Create: `template.html.liquid` (only the `{% raw %}` script block for now)
- Create: `test/fixtures/*.json` (saved real responses from 2026-11-14, one per source, plus hand-made edge cases)
- Create: `test/load.js`, which extracts the text between `{% raw %}` and `{% endraw %}` and evaluates it with `vm` to return `BTC`
- Test: `test/btc.test.js`

**Interfaces (Produces), all on `BTC`:**
- `balanceSats(addr) -> number|null`: (chain funded − chain spent) + (mempool funded − mempool spent). Returns null if `addr` lacks `chain_stats`.
- `txNet(tx, address) -> {sats: number, time: number|null, confirmed: boolean}`: the sum of `vout` values paying `address` minus the sum of `vin[].prevout` values from `address`. `time` is `status.block_time`, or null when unconfirmed.
- `recentTxs(txs, address, n) -> Array`: the first `n` mapped through `txNet`. Returns `[]` for a non-array input.
- `blockHeight(diff) -> number|null`: `nextRetargetHeight - remainingBlocks`.
- `halving(height, avgBlockMs) -> {blocks: number, date: Date}`: blocks up to the next multiple of 210,000 above `height`, with the date estimated from `avgBlockMs`.
- `priceChange(series, days) -> number|null`: percent change from the CoinGecko `prices` point `days` from the end to the last point.
- `fmtAmount(sats, unit, locale) -> string`: BTC with up to 8 decimals and trailing zeros trimmed to at least 2, or sats as a grouped integer followed by " sats".
- `fmtHashrate(hps) -> string`: `910870086509976000000` gives `"911 EH/s"`. Use ZH/s from 1e21 upward.
- `render(root, sources, opts)`: implemented in Task 2. `sources` is `{addr, txs, prices, diff, hash, fees, mempool, chart}`.

- [ ] **Step 1: Save fixtures.** Fetch the eight endpoints for `1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa` into `test/fixtures/`, keeping only 5 txs. Hand-write `tx-change.json`, which pays 1,000 sats in and spends a 5,000-sat input from the address, so the net is −4,000. Hand-write `addr-empty.json` with all zero stats, and `addr-pending.json` with mempool funded 50,000.
- [ ] **Step 2: Write failing tests** in `test/btc.test.js` using `node:test` and `assert/strict`:
  - `balanceSats(addr)` is `5771209980` for the genesis fixture, `0` for empty, and `50000` for pending. `balanceSats({error: 'x'})` is `null`.
  - `txNet(changeTx, A).sats === -4000`. An unconfirmed tx has `confirmed === false` and `time === null`.
  - `recentTxs(null, A, 2)` deep-equals `[]`.
  - `blockHeight({nextRetargetHeight: 977760, remainingBlocks: 1979}) === 975781`. `blockHeight(null) === null`.
  - `halving(975781, 600000).blocks === 74219`.
  - `priceChange([[0,100],[1,110]], 1) === 10`. `priceChange(undefined, 7) === null`.
  - `fmtAmount(1000, 'BTC', 'en-GB') === '0.00001 BTC'`. `fmtAmount(200000000000, 'sats', 'en-GB') === '200,000,000,000 sats'`. `fmtAmount(150000000, 'BTC', 'en-GB') === '1.50 BTC'`.
  - `fmtHashrate(910870086509976000000) === '911 EH/s'`.
- [ ] **Step 3: Run** `node --test test/`. Expected: FAIL, because `BTC` is undefined.
- [ ] **Step 4: Implement** the functions above in the raw block of `template.html.liquid`, ending with `if (typeof module !== 'undefined') module.exports = BTC;`.
- [ ] **Step 5: Run** `node --test test/`. Expected: all pass.
- [ ] **Step 6: Commit** with "Add the data functions for the Bitcoin extension".

### Task 2: Screen layout, configuration and render check

**Files:**
- Modify: `template.html.liquid`, adding the markup, styles, `render`, and the bootstrap that reads `data-*` attributes for `source_1`…`source_8`
- Create: `configuration.yml`
- Create: `test/render.mjs`, which renders the Liquid with liquidjs using the fixtures as `source_N` and `extension.values` from the config defaults, wraps it in the TRMNL framework CSS and JS (`https://trmnl.com/css/latest/plugins.css`, `https://trmnl.com/js/latest/plugins.js`) inside `<div class="screen">`, and screenshots it with Playwright at 800×480 and 480×800 into `test/out/`
- Create: `.gitignore` containing `node_modules/`, `test/out/`, `*.zip`
- Create: `package.json` with dev-only dependencies on `liquidjs` and `playwright`, and the scripts `test` and `render`

**Interfaces:** consumes all Task 1 functions.

- [ ] **Step 1: Write a failing test**, `render fills every section`, in `test/btc.test.js`. It uses a minimal DOM stub, or calls `render` with a root object whose `innerHTML` setter captures the string. With all fixtures, the HTML contains `57.71209980 BTC` or the trimmed form `57.7120998 BTC`, `975,781`, `911 EH/s`, and two transaction rows. With `{}` as sources, it contains `Address unavailable` and `—`, and it does not throw.
- [ ] **Step 2: Run** `node --test test/`. Expected: the new test fails.
- [ ] **Step 3: Implement `render`** and the markup, following the spec's screen sketch. Use a `.btc-portrait` class added by the same viewport check the weather template uses. Draw the chart as an inline SVG polyline with a 2px black stroke and no fill. Write the title bar as `label`, the shortened address, and "Updated HH:MM" from `prices.time`.
- [ ] **Step 4: Write `configuration.yml`**, modelled on the weather file, with the fields, `data.values` defaults, and one exchange whose template holds the eight URLs separated by spaces, using `{{ extension.values.api_base }}`, `{{ extension.values.address }}`, and `{{ extension.values.currency | downcase }}` for CoinGecko.
- [ ] **Step 5: Run** `node --test test/`. Expected: all pass.
- [ ] **Step 6: Run** `npm run render`, then open both PNGs. Expected: there is no overflow or clipped text in either orientation, every section shows, and the chart is visible.
- [ ] **Step 7: Commit** with "Add the Bitcoin screen and Terminus configuration".

### Task 3: README

**Files:**
- Create: `README.md`, with the same sections as `../weather-trmnl/README.md`: what the screen shows, how it works (the source table), setup (zip only the two files, upload, set `address`, choose the model, build, add to the playlist), settings, keeping copies in sync, and the license. Add a privacy note: mempool.space sees the address, so set `api_base` to a self-hosted mempool server to avoid that.

- [ ] **Step 1: Write the README.** It follows the relay-voice rules.
- [ ] **Step 2: Check** that `zip extension.zip configuration.yml template.html.liquid` produces a zip with exactly two entries, using `unzip -l`.
- [ ] **Step 3: Commit** with "Add the README".
