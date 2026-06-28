"""GitHub device auth poller — writes code to file"""
import requests, sys, time, os

r = requests.post('https://github.com/login/device/code',
    headers={'Accept': 'application/json'},
    data={'client_id': '01ab8ac9400c4e429b23', 'scope': 'repo,read:org,notifications'})
data = r.json()
dc = data['device_code']
uc = data['user_code']
interval = data.get('interval', 5)
expires = data.get('expires_in', 899)

# Write code to a known file
out_path = '/tmp/gh_device_code.txt'
with open(out_path, 'w') as f:
    f.write(f'{uc}\n')
    f.write(f'{dc}\n')
    f.write(f'{interval}\n')
    f.write(f'{expires}\n')
os.chmod(out_path, 0o644)

print(f'CODE:{uc}', flush=True)
print(f'URL:https://github.com/login/device', flush=True)
print(f'Written to {out_path}', flush=True)

start = time.time()
while time.time() - start < expires:
    r2 = requests.post('https://github.com/login/oauth/access_token',
        headers={'Accept': 'application/json'},
        data={
            'client_id': '01ab8ac9400c4e429b23',
            'device_code': dc,
            'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'
        })
    td = r2.json()
    if 'access_token' in td:
        token = td['access_token']
        with open('/tmp/gh_token.txt', 'w') as f:
            f.write(token)
        os.chmod('/tmp/gh_token.txt', 0o644)
        print(f'\nTOKEN_OK', flush=True)
        # Check notifications
        r3 = requests.get('https://api.github.com/notifications',
            headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github.v3+json'})
        notifs = r3.json()
        print(f'NOTIFS:{len(notifs)}', flush=True)
        for n in notifs[:30]:
            subj = n.get('subject', {})
            repo = n.get('repository', {}).get('full_name', '?')
            reason = n.get('reason', '?')
            title = subj.get('title', '?')
            print(f'  [{reason}] {repo} | {title[:80]}', flush=True)
        sys.exit(0)
    elif td.get('error') == 'authorization_pending':
        print('.', end='', flush=True)
    elif td.get('error') == 'slow_down':
        interval += 5
    time.sleep(interval)

print('\nTIMEOUT', flush=True)
