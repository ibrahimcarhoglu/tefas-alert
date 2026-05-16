from pytefas import Crawler
import pandas as pd

c = Crawler()
print("Methods in pytefas.Crawler:")
print([m for m in dir(c) if not m.startswith('_')])

try:
    print("\nFetching current funds...")
    # Many crawlers have a fetch() or similar
    df = c.fetch(date="2026-05-15")
    print(df.head())
except Exception as e:
    print(f"Error in fetch: {e}")
