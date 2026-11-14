// Reads the flat `data.values` map from configuration.yml without a YAML dependency.
export default {
  dataValues(text) {
    const lines = text.split('\n');
    const start = lines.findIndex((l) => l === '  values:');
    const values = {};
    for (const line of lines.slice(start + 1)) {
      const m = line.match(/^ {4}(\w+): (.*)$/);
      if (!m) break;
      values[m[1]] = m[2].replace(/^'(.*)'$/, '$1');
    }
    return values;
  }
};
