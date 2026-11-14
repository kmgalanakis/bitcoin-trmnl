// Renders template.html.liquid the way Terminus does, using the saved fixtures, and screenshots it.
// Usage: npm run render   (writes test/out/landscape.png and test/out/portrait.png)
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Liquid } from 'liquidjs';
import { chromium } from 'playwright';
import YAML from './yaml-lite.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, '..');
const out = path.join(here, 'out');
fs.mkdirSync(out, { recursive: true });

const fixture = (name) => JSON.parse(fs.readFileSync(path.join(here, 'fixtures', name + '.json'), 'utf8'));
const values = YAML.dataValues(fs.readFileSync(path.join(root, 'configuration.yml'), 'utf8'));
const sources = ['addr', 'txs', 'prices', 'diff', 'hash', 'fees', 'mempool', 'chart'];

const engine = new Liquid();
engine.registerFilter('jsonify', (v) => JSON.stringify(v ?? null));
const template = fs.readFileSync(path.join(root, 'template.html.liquid'), 'utf8');

// Terminus layout: app/templates/layouts/extension.html.erb
const page = (body) => `<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://trmnl.com/css/latest/plugins.css">
<style>:where(body){align-items:center;display:flex;flex-direction:column;justify-content:center}</style>
<script src="https://trmnl.com/js/latest/plugins.js"></script>
</head><body class="trmnl">${body}</body></html>`;

const variants = (process.argv[2] || 'all') === 'all' ? ['landscape', 'portrait'] : [process.argv[2]];
const scenario = process.env.SCENARIO || 'full';

// Uses a cached Playwright Chromium when the matching build is not installed: CHROMIUM=/path npm run render
const browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
for (const orientation of variants) {
  const context = {
    extension: {
      values,
      css_classes: `screen screen--og screen--2bit screen--${orientation} screen--md screen--1x`
    }
  };
  sources.forEach((name, i) => {
    if (scenario === 'empty') return;
    context[`source_${i + 1}`] = fixture(name);
  });
  const html = page(await engine.parseAndRender(template, context));
  fs.writeFileSync(path.join(out, `${orientation}.html`), html);

  const size = orientation === 'portrait' ? { width: 480, height: 800 } : { width: 800, height: 480 };
  const tab = await browser.newPage({ viewport: size });
  const errors = [];
  tab.on('pageerror', (e) => errors.push(e.message));
  tab.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  await tab.setContent(html, { waitUntil: 'networkidle' });
  await tab.waitForTimeout(500);
  const file = path.join(out, `${scenario}-${orientation}.png`);
  await tab.screenshot({ path: file });
  const overflow = await tab.evaluate(() => [...document.querySelectorAll('#btc-root *')]
    .filter((el) => el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflow !== 'visible')
    .map((el) => el.className + ': ' + el.textContent.slice(0, 40)));
  console.log(file, errors.length ? 'ERRORS ' + errors.join(' | ') : 'no errors',
    overflow.length ? 'CLIPPED ' + overflow.join(' | ') : 'nothing clipped');
  await tab.close();
}
await browser.close();
