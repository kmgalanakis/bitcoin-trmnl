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
