import requests

url = "https://www.tefas.gov.tr/api/DB/BindVariableTable"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}

# Example payload for a date
payload = "fontip=YAT&sfontip=YAT&bastarih=30.04.2024&bittarih=30.04.2024&suratli=0"

print(f"Testing TEFAS API with requests...")
try:
    response = requests.post(url, headers=headers, data=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response Header Content-Type: {response.headers.get('Content-Type')}")
    if response.status_code == 200:
        print("Success! Data preview:")
        print(response.text[:500])
    else:
        print("Failed. Content:")
        print(response.text[:500])
except Exception as e:
    print(f"Error: {e}")
