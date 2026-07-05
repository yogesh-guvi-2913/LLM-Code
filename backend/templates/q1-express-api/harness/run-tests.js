#!/usr/bin/env node

const http = require('http');

const BASE_URL = 'http://localhost:3000';

let totalTests = 0;
let passedTests = 0;
let testResults = [];

async function makeRequest(method, path, body = null) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'localhost',
      port: 3000,
      path: path,
      method: method,
      headers: {
        'Content-Type': 'application/json',
      },
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(data) });
        } catch {
          resolve({ status: res.statusCode, body: data });
        }
      });
    });

    req.on('error', reject);
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

function runTest(name, fn) {
  totalTests++;
  return fn()
    .then(() => {
      passedTests++;
      testResults.push({ name, passed: true });
    })
    .catch((err) => {
      testResults.push({ name, passed: false, error: err.message });
    });
}

async function runTests() {
  console.log('Running tests...\n');

  await runTest('GET /api/items returns 200 array', async () => {
    const res = await makeRequest('GET', '/api/items');
    if (res.status !== 200) throw new Error(`Expected 200, got ${res.status}`);
    if (!Array.isArray(res.body)) throw new Error('Expected array response');
  });

  await runTest('POST /api/items creates item', async () => {
    const res = await makeRequest('POST', '/api/items', { name: 'Test Item' });
    if (res.status !== 201) throw new Error(`Expected 201, got ${res.status}`);
    if (!res.body.id) throw new Error('Expected id in response');
  });

  await runTest('GET /api/items/:id returns item', async () => {
    const createRes = await makeRequest('POST', '/api/items', { name: 'Get Test' });
    const id = createRes.body.id;
    const res = await makeRequest('GET', `/api/items/${id}`);
    if (res.status !== 200) throw new Error(`Expected 200, got ${res.status}`);
  });

  await runTest('PUT /api/items/:id updates item', async () => {
    const createRes = await makeRequest('POST', '/api/items', { name: 'Update Test' });
    const id = createRes.body.id;
    const res = await makeRequest('PUT', `/api/items/${id}`, { name: 'Updated' });
    if (res.status !== 200) throw new Error(`Expected 200, got ${res.status}`);
  });

  await runTest('DELETE /api/items/:id deletes item', async () => {
    const createRes = await makeRequest('POST', '/api/items', { name: 'Delete Test' });
    const id = createRes.body.id;
    const res = await makeRequest('DELETE', `/api/items/${id}`);
    if (res.status !== 200 && res.status !== 204) throw new Error(`Expected 200/204, got ${res.status}`);
  });

  const score = Math.round((passedTests / totalTests) * 100);
  const result = {
    score: score,
    max_score: 100,
    passed: passedTests,
    total: totalTests,
    test_results: testResults,
  };

  console.log(`\nScore: ${score}/100 (${passedTests}/${totalTests} tests passed)\n`);
  console.log(JSON.stringify(result, null, 2));
}

runTests().catch(console.error);