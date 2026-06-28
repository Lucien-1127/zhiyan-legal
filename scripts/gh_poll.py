"""GitHub device auth poller"""
import requests, sys, time

r = requests.post('https://github.com/login/device/code',
    headers={'Accept': 'application/json'},
    data={'client_id': '01ab8ac9400c4e429b23', 'scope': 'repo,read:org,notifications'})
data = r.json()
dc = data['device_code']
uc = data['user_code']
interval = data.get('interval', 5)
expires = data.get('expires_in', 899)

print(f'CODE:{uc}', flush=True)
print(f'URL:https://github.com/login/device', flush=True)

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
        print(f'\nTOKEN_OK', flush=True)
        # Save to gh
        import os
        os.environ['GH_TOKEN'] = token
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
