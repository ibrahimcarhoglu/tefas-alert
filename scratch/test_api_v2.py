import requests
import ssl
from urllib3.poolmanager import PoolManager
from requests.adapters import HTTPAdapter

class CustomHttpAdapter(HTTPAdapter):
    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize, block=block, ssl_context=self.ssl_context)

def get_session():
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
    session = requests.session()
    session.mount("https://", CustomHttpAdapter(ctx))
    return session

url = "https://fundturkey.com.tr/api/DB/BindHistoryInfo"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}

payload = {
    "fontip": "YAT",
    "bastarih": "30.04.2024",
    "bittarih": "30.04.2024",
    "fonkod": "",
}

print(f"Testing TEFAS API (BindHistoryInfo) with requests...")
session = get_session()
try:
    response = session.post(url, headers=headers, data=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Success! Data preview:")
        print(response.text[:500])
    else:
        print(f"Failed. Content: {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

# Try tefas.gov.tr as alternative
url2 = "https://www.tefas.gov.tr/api/DB/BindHistoryInfo"
print(f"\nTesting TEFAS API (tefas.gov.tr) with requests...")
try:
    response = session.post(url2, headers=headers, data=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Success!")
    else:
        print(f"Failed. Content: {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
