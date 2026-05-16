from tefas import Crawler
from datetime import datetime

tefas = Crawler()
try:
    print("Fetching data for 2026-05-15 (Friday)...")
    df = tefas.fetch(
        start="2026-05-15",
        end="2026-05-15",
        kind="YAT",
        columns=["code", "date", "price", "market_cap", "number_of_investors"]
    )
    if df is not None:
        print(f"Success! Fetched {len(df)} records.")
        print(df.head())
    else:
        print("Failed: No data returned.")
except Exception as e:
    print(f"Error: {e}")
