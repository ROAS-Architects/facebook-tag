// Runs the real redactUrlSecrets/maskSecret out of template.js, so this test
// cannot drift from the code it checks. Run: node scripts/test-redact.js
const assert = require('assert');
const fs = require('fs');

const src = fs.readFileSync('template.js', 'utf8');
const fns = ['redactUrlSecrets', 'maskSecret'].map((name) => {
  const m = src.match(new RegExp('^function ' + name + '\\([\\s\\S]*?^}', 'm'));
  assert.ok(m, name + ' not found in template.js');
  return m[0];
});
const { redactUrlSecrets } = new Function(fns.join('\n') + '\nreturn { redactUrlSecrets };')();

const TOKEN = 'EAAG1234567890abcdefghijklmnopqrstuvwxyzZZZZ';
const base = 'https://graph.facebook.com/v21.0/123456/events';

// The token is masked, and enough survives to tell two tokens apart.
let out = redactUrlSecrets(base + '?access_token=' + TOKEN);
assert.strictEqual(out, base + '?access_token=EAAG...ZZZZ');
assert.ok(!out.includes(TOKEN));

// Both secrets go, and the pixel id stays readable.
out = redactUrlSecrets(base + '?access_token=' + TOKEN + '&appsecret_proof=' + TOKEN);
assert.strictEqual(
  out,
  base + '?access_token=EAAG...ZZZZ&appsecret_proof=EAAG...ZZZZ'
);
assert.ok(out.includes('/123456/events'));

// A short secret is masked whole rather than mostly shown.
assert.strictEqual(
  redactUrlSecrets(base + '?access_token=short12chars'),
  base + '?access_token=[redacted]'
);

// A parameter after the token keeps its place and its value.
assert.strictEqual(
  redactUrlSecrets(base + '?access_token=' + TOKEN + '&fields=id'),
  base + '?access_token=EAAG...ZZZZ&fields=id'
);

// A URL with no secrets is returned untouched.
assert.strictEqual(redactUrlSecrets(base), base);

console.log('test-redact: ok');
