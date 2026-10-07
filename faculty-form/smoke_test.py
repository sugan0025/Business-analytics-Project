import requests
import time

base_url = 'https://faculty-selection-bitsathy.vercel.app'

print('--- 1. Testing Healthz ---')
for i in range(12):
    try:
        t0 = time.time()
        r = requests.get(f'{base_url}/healthz', timeout=10)
        dt = (time.time() - t0) * 1000
        if r.status_code == 200:
            print(f'Healthz OK: status=200, latency={dt:.0f}ms')
            print('Healthz JSON:', r.json())
            break
    except Exception as e:
        print(f'Retry {i+1}: {e}')
    time.sleep(3)

print('\n--- 2. Triggering Full Rewrite & Resequence to Google Sheet ---')
t0 = time.time()
r_sync = requests.post(
    f'{base_url}/api/sync?full=1',
    headers={'X-Sync-Token': 'bitsathy-sync-2026'},
    timeout=25
)
dt = (time.time() - t0) * 1000
print(f'Sync Full Rewrite Status: {r_sync.status_code}, Latency: {dt:.0f}ms')
print('Sync Result:', r_sync.text)

print('\n--- 3. Testing Availability Live ---')
t0 = time.time()
r_avail = requests.get(f'{base_url}/api/availability', timeout=10)
dt = (time.time() - t0) * 1000
print(f'Availability Status: {r_avail.status_code}, Latency: {dt:.0f}ms')
avail_data = r_avail.json().get('faculty', [])
for f in avail_data:
    print(f"  {f['name']}: Capacity={f['capacity']}, Remaining={f['remaining']}")
