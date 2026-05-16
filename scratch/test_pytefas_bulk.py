from pytefas import Crawler
import pandas as pd

c = Crawler()
try:
    print("Fetching all YAT funds for 2026-05-15...")
    df = c.fetch(start="2026-05-15", end="2026-05-15", kind="YAT")
    print(f"Success! Fetched {len(df)} records.")
    print(df.columns.tolist())
    print(df.head())
except Exception as e:
    print(f"Error: {e}")
