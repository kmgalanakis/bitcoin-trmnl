// Loads the BTC module from the {% raw %} block of the Liquid template, so Node can test it.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const TEMPLATE = path.join(__dirname, '..', 'template.html.liquid');

function load() {
  const source = fs.readFileSync(TEMPLATE, 'utf8');
  const start = source.indexOf('{% raw %}');
  const end = source.indexOf('{% endraw %}');
  if (start < 0 || end < start) throw new Error('No {% raw %} block in template.html.liquid');
  const module = { exports: {} };
  vm.runInNewContext(source.slice(start + 9, end), { module, Intl, Date, Math, Number, String, Array, JSON, isFinite });
  return module.exports;
}

const fixture = (name) => JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', name + '.json'), 'utf8'));

module.exports = { load, fixture };
