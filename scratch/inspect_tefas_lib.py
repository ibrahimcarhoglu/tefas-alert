from tefas import Crawler
import pandas as pd

tefas = Crawler()
try:
    df = tefas.fetch(start="2026-05-15", end="2026-05-15", kind="YAT")
    print(f"Columns: {df.columns.tolist()}")
    print(df.head())
except Exception as e:
    print(f"Error: {e}")
