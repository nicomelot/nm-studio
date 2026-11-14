const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');

test('new record and request IDs work on HTTP ingress without randomUUID', () => {
  const source = fs.readFileSync(require('node:path').join(__dirname, '../nm_bridge/control.js'), 'utf8');
  const declaration = source.slice(source.indexOf('const uid='), source.indexOf('const fmt='));
  const uid = vm.runInNewContext(declaration + '\nuid', {
    crypto: { getRandomValues: a => webcrypto.getRandomValues(a) }, Uint8Array
  });
  const ids = Array.from({length:100}, () => uid());
  assert.equal(new Set(ids).size, 100);
  for (const id of ids) assert.match(id, /^[a-zA-Z0-9_-]{1,80}$/);
});
