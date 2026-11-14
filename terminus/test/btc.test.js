const test = require('node:test');
const assert = require('node:assert/strict');
const { load, fixture } = require('./load');

const BTC = load();
const GENESIS = '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa';
const TEST_ADDR = 'bc1qtestaddress0000000000000000000000000';

test('balanceSats adds confirmed and pending funds', () => {
  assert.equal(BTC.balanceSats(fixture('addr')), 5771209980);
  assert.equal(BTC.balanceSats(fixture('addr-empty')), 0);
  assert.equal(BTC.balanceSats(fixture('addr-pending')), 50000);
  assert.equal(BTC.balanceSats({ error: 'x' }), null);
  assert.equal(BTC.balanceSats(null), null);
});

test('txNet nets change outputs against inputs', () => {
  const change = BTC.txNet(fixture('tx-change'), TEST_ADDR);
  assert.equal(change.sats, -4000);
  assert.equal(change.confirmed, true);
  assert.equal(change.time, 1794000000);
});

test('txNet marks unconfirmed transactions as pending', () => {
  const pending = BTC.txNet(fixture('tx-pending'), TEST_ADDR);
  assert.equal(pending.sats, 50000);
  assert.equal(pending.confirmed, false);
  assert.equal(pending.time, null);
});

test('recentTxs takes the first n and tolerates bad input', () => {
  const txs = BTC.recentTxs(fixture('txs'), GENESIS, 2);
  assert.equal(txs.length, 2);
  assert.equal(txs[0].sats, 546);
  assert.equal(BTC.recentTxs(null, GENESIS, 2).length, 0);
  assert.equal(BTC.recentTxs({ error: "x" }, GENESIS, 2).length, 0);
});

test('blockHeight comes from the difficulty adjustment', () => {
  assert.equal(BTC.blockHeight({ nextRetargetHeight: 977760, remainingBlocks: 1979 }), 975781);
  assert.equal(BTC.blockHeight(null), null);
  assert.equal(BTC.blockHeight({}), null);
});

test('halving counts blocks to the next multiple of 210,000', () => {
  const h = BTC.halving(975781, 600000);
  assert.equal(h.blocks, 74219);
  assert.equal(h.date.getTime() - Date.now() > 74219 * 600000 - 60000, true);
  assert.equal(BTC.halving(1050000, 600000).blocks, 210000);
  assert.equal(BTC.halving(null, 600000), null);
});

test('priceChange compares the last point with one n days earlier', () => {
  assert.equal(BTC.priceChange([[0, 100], [1, 110]], 1), 10);
  assert.equal(BTC.priceChange(undefined, 7), null);
  assert.equal(BTC.priceChange([[0, 100]], 7), null);
});

test('fmtAmount formats BTC and sats on one line', () => {
  assert.equal(BTC.fmtAmount(1000, 'BTC', 'en-GB'), '0.00001 BTC');
  assert.equal(BTC.fmtAmount(150000000, 'BTC', 'en-GB'), '1.50 BTC');
  assert.equal(BTC.fmtAmount(200000000000, 'BTC', 'en-GB'), '2,000.00 BTC');
  assert.equal(BTC.fmtAmount(200000000000, 'sats', 'en-GB'), '200,000,000,000 sats');
  assert.equal(BTC.fmtAmount(null, 'BTC', 'en-GB'), '—');
});

test('fmtHashrate picks EH/s or ZH/s', () => {
  assert.equal(BTC.fmtHashrate(910870086509976000000), '911 EH/s');
  assert.equal(BTC.fmtHashrate(1.2e21), '1.2 ZH/s');
  assert.equal(BTC.fmtHashrate(undefined), '—');
});

const ALL = () => ({
  addr: fixture('addr'), txs: fixture('txs'), prices: fixture('prices'), diff: fixture('diff'),
  hash: fixture('hash'), fees: fixture('fees'), mempool: fixture('mempool'), chart: fixture('chart')
});
const OPTS = { address: GENESIS, currency: 'EUR', unit: 'BTC', locale: 'en-GB' };

test('render fills every section', () => {
  const root = { innerHTML: '' };
  const s = ALL();
  const result = BTC.render(root, s, OPTS);
  const html = root.innerHTML;
  assert.match(html.replace(/<[^>]+>/g, ''), /57\.7120998 BTC/);
  assert.match(html, new RegExp(BTC.blockHeight(s.diff).toLocaleString('en-GB')));
  assert.match(html, new RegExp(BTC.fmtHashrate(s.hash.currentHashrate).replace('/', '\\/')));
  assert.match(html, /<polyline/);
  assert.equal((html.match(/class="btc-tx"/g) || []).length, 2);
  assert.match(result.updated, /^\d{2}:\d{2}$/);
});

test('render survives missing sources', () => {
  const root = { innerHTML: '' };
  const result = BTC.render(root, {}, OPTS);
  assert.match(root.innerHTML, /Address unavailable/);
  assert.match(root.innerHTML, /—/);
  assert.doesNotMatch(root.innerHTML, /<polyline/);
  assert.equal(result.updated, '');
});

test('render treats error objects like missing data', () => {
  const root = { innerHTML: '' };
  const err = { error: 'Bad fetch' };
  BTC.render(root, { addr: err, txs: err, prices: err, diff: err, hash: err, fees: err, mempool: err, chart: err }, OPTS);
  assert.match(root.innerHTML, /Address unavailable/);
});

test('render shows an empty wallet', () => {
  const root = { innerHTML: '' };
  BTC.render(root, { addr: fixture('addr-empty'), txs: [] }, { ...OPTS, address: TEST_ADDR });
  assert.match(root.innerHTML.replace(/<[^>]+>/g, ''), /0\.00 BTC/);
  assert.match(root.innerHTML, /No transactions yet/);
});

test('render marks a pending transaction', () => {
  const root = { innerHTML: '' };
  BTC.render(root, { addr: fixture('addr-pending'), txs: [fixture('tx-pending')] }, { ...OPTS, address: TEST_ADDR });
  assert.match(root.innerHTML, /\+0\.0005 BTC/);
  assert.match(root.innerHTML, /pending/i);
});

test('balanceSats reads a wallet scan', () => {
  assert.equal(BTC.balanceSats(fixture('wallet')), 123456789);
});

test('recentTxs uses the wallet scan rows as they are', () => {
  const txs = BTC.recentTxs(fixture('wallet'), 'ignored', 2);
  assert.equal(txs.length, 2);
  assert.equal(txs[0].sats, 50000);
  assert.equal(txs[0].confirmed, false);
  assert.equal(txs[1].sats, -31000);
});

test('render shows a whole wallet', () => {
  const root = { innerHTML: '' };
  const w = fixture('wallet');
  const result = BTC.render(root, { addr: w, txs: w, prices: fixture('prices') }, { ...OPTS, address: '' });
  const text = root.innerHTML.replace(/<[^>]+>/g, '');
  assert.match(text, /1\.23456789 BTC/);
  assert.match(text, /\+0\.0005 BTC/);
  assert.match(text, /−0\.00031 BTC/);
  assert.match(text, /Pending/);
  assert.equal((root.innerHTML.match(/class="btc-tx"/g) || []).length, 2);
  assert.equal(result.address, '7 addresses');
});

test('render keeps single-address mode when the wallet URL is not used', () => {
  const root = { innerHTML: '' };
  const result = BTC.render(root, { addr: fixture('addr'), txs: fixture('txs') }, OPTS);
  assert.equal(result.address, '1A1zP1…vfNa');
});

test('render defaults to US dollars when no currency is set', () => {
  const root = { innerHTML: '' };
  const { currency, ...noCurrency } = OPTS;
  BTC.render(root, { addr: fixture('addr'), prices: fixture('prices') }, noCurrency);
  const usd = fixture('prices').USD.toLocaleString('en-GB');
  assert.match(root.innerHTML, new RegExp('>\\$' + usd + '<'));
  assert.doesNotMatch(root.innerHTML, /US\$/);
});
