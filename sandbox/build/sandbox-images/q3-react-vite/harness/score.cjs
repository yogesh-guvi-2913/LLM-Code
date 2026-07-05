// score.cjs — reads vitest's JSON report and emits the exact score JSON the
// orchestrator expects as the last stdout line:
//   {"score":N,"max_score":100,"test_results":[...]}
//
// Each test title carries its weight inline as "[weight:N]" (see App.test.tsx),
// so the weights live in one place and always sum to 100.
const fs = require('fs');

const REPORT = process.env.VITEST_REPORT || '/tmp/vitest-results.json';

function emit(score, results) {
  process.stdout.write(
    JSON.stringify({ score, max_score: 100, test_results: results }) + '\n',
  );
}

let report;
try {
  report = JSON.parse(fs.readFileSync(REPORT, 'utf8'));
} catch (e) {
  // No parseable report => the suite failed to run at all (e.g. App.tsx doesn't
  // compile). Score 0 rather than crashing the scorer.
  emit(0, [
    { name: 'vitest run', passed: false, error: 'no test report produced', duration_ms: 0 },
  ]);
  process.exit(0);
}

const assertions = [];
for (const file of report.testResults || []) {
  for (const a of file.assertionResults || []) assertions.push(a);
}

let score = 0;
const results = [];
for (const a of assertions) {
  const title = a.title || a.fullName || 'unnamed';
  const m = /\[weight:(\d+)\]/.exec(title);
  const weight = m ? Number(m[1]) : 0;
  const passed = a.status === 'passed';
  if (passed) score += weight;
  results.push({
    name: title,
    passed,
    weight,
    duration_ms: a.duration != null ? Math.round(a.duration) : 0,
    error: passed ? undefined : (a.failureMessages || []).join('\n').slice(0, 500) || 'failed',
  });
}

// Clamp defensively; weights are authored to sum to 100.
if (score > 100) score = 100;
emit(score, results);
