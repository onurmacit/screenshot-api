import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
    stages: [
        { duration: '1m', target: 10 },  // Ramp up to 10 users
        { duration: '3m', target: 10 },  // Stay at 10 users
        { duration: '1m', target: 50 },  // Spike to 50 users
        { duration: '2m', target: 50 },  // Stay at 50 users
        { duration: '1m', target: 0 },   // Ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<500'], // 95% of requests under 500ms
        http_req_failed: ['rate<0.01'],   // <1% failure rate
    },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

export default function () {
    // Test health endpoint
    let healthRes = http.get(`${BASE_URL}/api/v1/health`);
    check(healthRes, {
        'health status is 200': (r) => r.status === 200,
        'health response has status': (r) => r.json('status') === 'healthy',
    });

    sleep(1);
}
