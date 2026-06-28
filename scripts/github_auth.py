"""GitHub device auth flow — background poll for token"""
import json
import os
import time
import requests
from pathlib import Path

# Step 1: Get device code
print("Requesting device code...")
r = requests.post("https://github.com/login/device/code",
    headers={"Accept": "application/json"},
    data={"client_id": "01ab8ac9400c4e429b23", "scope": "repo,read:org,notifications"},
)
data = r.json()
user_code = data["user_code"]
device_code = data["device_code"]
interval = data.get("interval", 5)
expires_in = data.get("expires_in", 899)

print(f"\n🔑 DEVICE CODE: {user_code}")
print(f"🌐 Go to: https://github.com/login/device")
print(f"⏱  Expires in {expires_in}s")
print("\nPolling every {}s for authorization...".format(interval))

# Step 2: Poll for token
start = time.time()
while time.time() - start < expires_in:
    r2 = requests.post("https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": "01ab8ac9400c4e429b23",
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        },
    )
    token_data = r2.json()
    
    if "access_token" in token_data:
        token = token_data["access_token"]
        print(f"\n✅ Token obtained! ({len(token)} chars)")
        
        # Save token to gh config
        config_dir = Path.home() / ".config" / "gh"
        config_dir.mkdir(parents=True, exist_ok=True)
        hosts_file = config_dir / "hosts.yml"
        
        # Also set env var for this session
        os.environ["GH_TOKEN"] = token
        
        print(f"GH_TOKEN set in environment")
        
        # Test the token
        r3 = requests.get("https://api.github.com/user",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"})
        user = r3.json()
        print(f"Authenticated as: {user.get('login', '?')}")
        
        # Get notifications
        r4 = requests.get("https://api.github.com/notifications",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"})
        notifs = r4.json()
        print(f"\n📬 Notifications: {len(notifs)}")
        for n in notifs[:20]:
            subject = n.get("subject", {})
            repo = n.get("repository", {}).get("full_name", "?")
            print(f"  [{n.get('reason','?')}] {repo}: {subject.get('title','?')} ({subject.get('type','?')})")
        break
    elif token_data.get("error") == "authorization_pending":
        # User hasn't entered code yet
        pass
    elif token_data.get("error") == "slow_down":
        interval += 5
    else:
        error = token_data.get("error", "unknown")
        error_desc = token_data.get("error_description", "")
        if error not in ("authorization_pending",):
            print(f"  Status: {error} {error_desc}")
    
    time.sleep(interval)
else:
    print("\n⏰ Timed out waiting for authorization.")
