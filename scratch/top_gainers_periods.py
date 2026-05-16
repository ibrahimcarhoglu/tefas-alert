from pytefas import Crawler
import pandas as pd
from datetime import datetime, timedelta

def get_top_gainers_for_periods():
    c = Crawler()
    latest_date_str = "2026-05-15"
    latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d")
    
    periods = {
        "3 Gün": 3,
        "1 Hafta": 7,
        "2 Hafta": 14,
        "1 Ay": 30,
        "7 Hafta": 49
    }
    
    print(f"Fetching latest data for {latest_date_str}...")
    df_latest = c.fetch(start=latest_date_str, end=latest_date_str, kind="YAT")
    if df_latest is None or df_latest.empty:
        print("No data for latest date.")
        return
    
    df_latest = df_latest[['fund_code', 'fund_name', 'price']].rename(columns={'price': 'price_latest'})
    
    results = {}
    
    for label, days in periods.items():
        target_date = latest_date - timedelta(days=days)
        found = False
        for i in range(5): 
            check_date = (target_date - timedelta(days=i)).strftime("%Y-%m-%d")
            print(f"Checking {label} ({days} days ago) -> trying {check_date}...")
            df_prev = c.fetch(start=check_date, end=check_date, kind="YAT")
            if df_prev is not None and not df_prev.empty:
                df_prev = df_prev[['fund_code', 'price']].rename(columns={'price': 'price_prev'})
                df = pd.merge(df_latest, df_prev, on='fund_code')
                df['pct_change'] = (df['price_latest'] - df['price_prev']) / df['price_prev'] * 100
                top_20 = df.sort_values(by='pct_change', ascending=False).head(20)
                results[label] = {
                    "date": check_date,
                    "data": top_20
                }
                found = True
                break
        if not found:
            print(f"Could not find data for {label} around {target_date.strftime('%Y-%m-%d')}")

    for label, info in results.items():
        print(f"\n--- {label} (Kıyaslama Tarihi: {info['date']}) ---")
        print(f"{'Kod':<6} {'Değişim':<10} {'Fon Adı'}")
        print("-" * 80)
        for _, row in info['data'].iterrows():
            print(f"{row['fund_code']:<6} {row['pct_change']:>8.2f}%   {row['fund_name']}")

if __name__ == "__main__":
    get_top_gainers_for_periods()
