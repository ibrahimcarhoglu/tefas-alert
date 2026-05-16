from pytefas import Crawler
import pandas as pd

c = Crawler()
try:
    print("Fetching single fund AU1 for 2026-05-15...")
    df = c.fetch(start="2026-05-15", end="2026-05-15", fund_code="AU1")
    print(df.columns.tolist())
    print(df.iloc[0])
except Exception as e:
    print(f"Error: {e}")
