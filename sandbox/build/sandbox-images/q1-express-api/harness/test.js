// test.js — exercises the candidate's todo API over loopback and emits the exact
// score JSON the orchestrator expects on stdout:
//   {"score":N,"max_score":M,"test_results":[...]}
const http = require('http');

function req(method, path, body) {
  return new Promise((resolve) => {
    const data = body ? JSON.stringify(body) : null;
    const r = http.request(
      { host: '127.0.0.1', port: 3000, method, path,
        headers: { 'Content-Type': 'application/json' } },
      (res) => {
        let buf = '';
        res.on('data', (c) => (buf += c));
        res.on('end', () => {
          let json = null;
          try { json = buf ? JSON.parse(buf) : null; } catch (_) {}
          resolve({ status: res.statusCode, body: json });
        });
      }
    );
    r.on('error', () => resolve({ status: 0, body: null }));
    if (data) r.write(data);
    r.end();
  });
}

async function run() {
  const cases = [
    { name: 'GET /todos returns 200 array', weight: 25, fn: async () => {
        const r = await req('GET', '/todos');
        if (r.status !== 200) throw new Error(`status ${r.status}`);
        if (!Array.isArray(r.body)) throw new Error('not an array');
      } },
    { name: 'POST /todos creates (201)', weight: 35, fn: async () => {
        const r = await req('POST', '/todos', { title: 'buy milk' });
        if (r.status !== 201) throw new Error(`status ${r.status}`);
        if (!r.body || r.body.title !== 'buy milk') throw new Error('title not echoed');
        if (r.body.id == null) throw new Error('no id');
      } },
    { name: 'GET /todos/:id returns created', weight: 40, fn: async () => {
        const c = await req('POST', '/todos', { title: 'walk dog' });
        if (c.status !== 201 || c.body.id == null) throw new Error('create failed');
        const r = await req('GET', `/todos/${c.body.id}`);
        if (r.status !== 200) throw new Error(`status ${r.status}`);
        if (!r.body || r.body.title !== 'walk dog') throw new Error('wrong todo');
      } },
  ];

  let score = 0;
  const results = [];
  for (const c of cases) {
    const start = Date.now();
    try {
      await c.fn();
      score += c.weight;
      results.push({ name: c.name, passed: true, duration_ms: Date.now() - start });
    } catch (e) {
      results.push({ name: c.name, passed: false, error: String(e.message || e), duration_ms: Date.now() - start });
    }
  }

  process.stdout.write(JSON.stringify({ score, max_score: 100, test_results: results }) + '\n');
}

run();
