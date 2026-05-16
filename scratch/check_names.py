from pytefas import Crawler
import pandas as pd

c = Crawler()
try:
    df = c.fetch(start="2026-05-15", end="2026-05-15", kind="YAT")
    # Show some sample names to see if they contain categories
    print(df[['fund_code', 'fund_name']].head(20))
except Exception as e:
    print(f"Error: {e}")
