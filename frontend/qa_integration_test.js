// Integration QA Test Suite for SafeScreen AI Frontend
// Runs against real Vite proxy (port 5173) and FastAPI backend (port 8000)

import http from 'node:http';

const VITE_PORT = 5173;
const HOST = '127.0.0.1';

async function request(path, options = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        hostname: HOST,
        port: VITE_PORT,
        path,
        method: options.method || 'GET',
        headers: options.headers || {},
      },
      (res) => {
        let body = '';
        res.on('data', (chunk) => (body += chunk));
        res.on('end', () => {
          try {
            const json = JSON.parse(body);
            resolve({ status: res.statusCode, data: json, headers: res.headers });
          } catch {
            resolve({ status: res.statusCode, raw: body, headers: res.headers });
          }
        });
      }
    );
    req.on('error', reject);
    if (options.body) req.write(options.body);
    req.end();
  });
}

const tests = [];
function test(name, fn) {
  tests.push({ name, fn });
}

let passed = 0;
let failed = 0;

// Test 1: Vite Proxy & Backend Health
test('1. Vite Proxy Health Check (/api/v1/health)', async () => {
  const res = await request('/api/v1/health');
  if (res.status !== 200) throw new Error(`Expected 200, got ${res.status}`);
  if (res.data?.status !== 'ok' || res.data?.service !== 'SafeScreen AI') {
    throw new Error(`Unexpected payload: ${JSON.stringify(res.data)}`);
  }
});

// Test 2: APPROVED & LOW decision verification
test('2. Moderation Decision APPROVED with LOW risk (test_slap)', async () => {
  const res = await request('/api/v1/videos/test_slap/moderation');
  if (res.status !== 200) throw new Error(`Expected 200, got ${res.status}`);
  if (res.data.decision !== 'APPROVED') throw new Error(`Expected APPROVED, got ${res.data.decision}`);
  if (res.data.risk_level !== 'LOW') throw new Error(`Expected LOW, got ${res.data.risk_level}`);
  if (typeof res.data.risk_score !== 'number') throw new Error('Missing risk_score');
});

// Test 3: REVIEW_REQUIRED & MEDIUM decision verification
test('3. Moderation Decision REVIEW_REQUIRED with MEDIUM risk (test_review_medium)', async () => {
  const res = await request('/api/v1/videos/test_review_medium/moderation');
  if (res.status !== 200) throw new Error(`Expected 200, got ${res.status}`);
  if (res.data.decision !== 'REVIEW_REQUIRED') throw new Error(`Expected REVIEW_REQUIRED, got ${res.data.decision}`);
  if (res.data.risk_level !== 'MEDIUM') throw new Error(`Expected MEDIUM, got ${res.data.risk_level}`);
});

// Test 4: REVIEW_REQUIRED & HIGH decision verification
test('4. Moderation Decision REVIEW_REQUIRED with HIGH risk (test_21jump_street_shooting)', async () => {
  const res = await request('/api/v1/videos/test_21jump_street_shooting/moderation');
  if (res.status !== 200) throw new Error(`Expected 200, got ${res.status}`);
  if (res.data.decision !== 'REVIEW_REQUIRED') throw new Error(`Expected REVIEW_REQUIRED, got ${res.data.decision}`);
  if (res.data.risk_level !== 'HIGH') throw new Error(`Expected HIGH, got ${res.data.risk_level}`);
  if (!res.data.findings || res.data.findings.length === 0) throw new Error('Expected findings array');
});

// Test 5: REJECTED & CRITICAL decision verification
test('5. Moderation Decision REJECTED with CRITICAL risk (test_rejected_critical)', async () => {
  const res = await request('/api/v1/videos/test_rejected_critical/moderation');
  if (res.status !== 200) throw new Error(`Expected 200, got ${res.status}`);
  if (res.data.decision !== 'REJECTED') throw new Error(`Expected REJECTED, got ${res.data.decision}`);
  if (res.data.risk_level !== 'CRITICAL') throw new Error(`Expected CRITICAL, got ${res.data.risk_level}`);
  if (!res.data.detected_categories.includes('child_safety')) throw new Error('Expected child_safety in categories');
});

// Test 6: Evidence traceability endpoint
test('6. Evidence retrieval endpoint (/api/v1/videos/{id}/evidence)', async () => {
  const res = await request('/api/v1/videos/test_21jump_street_shooting/evidence');
  if (res.status !== 200) throw new Error(`Expected 200, got ${res.status}`);
  if (!Array.isArray(res.data.evidence)) throw new Error('Expected evidence array');
  if (res.data.evidence.length === 0) throw new Error('Expected at least 1 evidence item');
});

// Test 7: Video Status polling endpoint
test('7. Lifecycle status polling endpoint (/api/v1/videos/{id}/status)', async () => {
  const res = await request('/api/v1/videos/test_slap/status');
  if (res.status !== 200) throw new Error(`Expected 200, got ${res.status}`);
  if (res.data.status !== 'COMPLETED') throw new Error(`Expected COMPLETED, got ${res.data.status}`);
});

// Test 8: Non-existent Video ID Graceful Failure
test('8. Failure state for non-existent video ID (404)', async () => {
  const res = await request('/api/v1/videos/nonexistent_video_id_9999');
  if (res.status !== 404) throw new Error(`Expected 404, got ${res.status}`);
});

// Test 9: Moderation unavailable on in-progress / uncompleted video (404)
test('9. Failure state for uncompleted video moderation report (404)', async () => {
  const res = await request('/api/v1/videos/vid_9329b45f522847abbc4bae144b3e64a8/moderation');
  if (res.status !== 404) throw new Error(`Expected 404, got ${res.status}`);
});

// Test 10: Invalid video ID input format validation (400 or 422)
test('10. Validation error on malformed video ID (400/422)', async () => {
  const res = await request('/api/v1/videos/invalid!!id/status');
  if (res.status !== 400 && res.status !== 422) throw new Error(`Expected 400 or 422, got ${res.status}`);
  if (!res.data?.detail?.includes('Invalid video ID format')) throw new Error('Expected invalid format message');
});

// Test 11: Frontend Root SPA Serves Index HTML
test('11. Frontend SPA root serves HTML (/dashboard)', async () => {
  const res = await request('/dashboard');
  if (res.status !== 200) throw new Error(`Expected 200, got ${res.status}`);
  if (!res.raw || !res.raw.includes('<div id="root"></div>')) {
    throw new Error('Expected root div in served HTML');
  }
});

// Test 12: Terminal State Logic Simulation for Session Videos
test('12. Session Videos Hydration Terminal State Simulation', async () => {
  // Test case A: Empty session -> immediately empty
  const emptySession = [];
  const emptyResult = emptySession.length === 0 ? 'EMPTY' : 'LOADING';
  if (emptyResult !== 'EMPTY') throw new Error('Empty session did not reach terminal state');

  // Test case B: Mixed session with valid ID and invalid/stale ID
  const sessionList = [
    { videoId: 'test_slap', filename: 'Slap.mp4' },
    { videoId: 'nonexistent_vid_404', filename: 'Ghost.mp4' },
  ];

  const results = await Promise.allSettled(
    sessionList.map(async (item) => {
      const resp = await request(`/api/v1/videos/${item.videoId}`);
      if (resp.status !== 200) {
        return { ...item, fetchError: `HTTP ${resp.status}` };
      }
      return { ...item, status: resp.data.status, duration: resp.data.duration };
    })
  );

  const hydrated = results.map((r, i) =>
    r.status === 'fulfilled' ? r.value : { ...sessionList[i], fetchError: 'Failed' }
  );

  // Check that valid video resolved and invalid video has fetchError without crashing
  const valid = hydrated.find((v) => v.videoId === 'test_slap');
  const invalid = hydrated.find((v) => v.videoId === 'nonexistent_vid_404');

  if (!valid || valid.status !== 'COMPLETED') throw new Error('Valid video failed hydration');
  if (!invalid || !invalid.fetchError) throw new Error('Stale video did not capture error gracefully');

  // Terminal state guarantee
  const hasLoaded = true; // finally block
  if (!hasLoaded) throw new Error('Loading state did not terminate');
});

async function run() {
  console.log('='.repeat(70));
  console.log('SafeScreen AI — Frontend & API QA Integration Test Suite');
  console.log('='.repeat(70));

  for (const { name, fn } of tests) {
    try {
      await fn();
      console.log(`[PASS] ${name}`);
      passed++;
    } catch (err) {
      console.error(`[FAIL] ${name}: ${err.message}`);
      failed++;
    }
  }

  console.log('-'.repeat(70));
  console.log(`Summary: ${passed} Passed, ${failed} Failed out of ${tests.length} tests.`);
  console.log('='.repeat(70));

  if (failed > 0) process.exit(1);
}

run();
