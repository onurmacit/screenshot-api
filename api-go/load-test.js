import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
    vus: 5,               // 5 Virtual Users
    duration: '30s',      // Run for 30 seconds
};

export default function () {
    const url = 'http://localhost:8080/api/v1/renders/demo';

    // Using dummy token works because we use Cloudflare Test Secret Key
    const payload = JSON.stringify({
        url: 'https://example.com',
        token: 'dummy-token',
    });

    const params = {
        headers: {
            'Content-Type': 'application/json',
        },
    };

    const res = http.post(url, payload, params);

    check(res, {
        'is status 200': (r) => r.status === 200,
        'response time < 5000ms': (r) => r.timings.duration < 5000,
    });

    // Sleep 1s to simulate user read time
    sleep(1);
}
