from pytefas import Crawler
import pandas as pd
from datetime import datetime, timedelta

def get_top_gainers(date_str, prev_date_str):
    c = Crawler()
    print(f"Fetching data for {date_str} and {prev_date_str}...")
    
    try:
        df_today = c.fetch(start=date_str, end=date_str, kind="YAT")
        df_prev = c.fetch(start=prev_date_str, end=prev_date_str, kind="YAT")
        
        if df_today is None or df_today.empty:
            print(f"No data for {date_str}")
            return
        if df_prev is None or df_prev.empty:
            print(f"No data for {prev_date_str}")
            return

        # Prepare dataframes
        df_today = df_today[['fund_code', 'price']].rename(columns={'price': 'price_today'})
        df_prev = df_prev[['fund_code', 'price']].rename(columns={'price': 'price_prev'})
        
        # Merge
        df = pd.merge(df_today, df_prev, on='fund_code')
        
        # Calculate percentage change
        df['pct_change'] = (df['price_today'] - df['price_prev']) / df['price_prev'] * 100
        
        # Sort and get top 10
        top_gainers = df.sort_values(by='pct_change', ascending=False).head(10)
        
        print(f"\nTop 10 Gainers ({date_str} vs {prev_date_str}):")
        print("-" * 50)
        print(f"{'Code':<10} {'Price Today':<15} {'Price Prev':<15} {'Change (%)':<10}")
        print("-" * 50)
        for _, row in top_gainers.iterrows():
            print(f"{row['fund_code']:<10} {row['price_today']:<15.6f} {row['price_prev']:<15.6f} {row['pct_change']:>8.2f}%")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Assuming today is 2026-05-16 (Saturday), 
    # last trading day is 2026-05-15 (Friday)
    # previous trading day is 2026-05-14 (Thursday)
    get_top_gainers("2026-05-15", "2026-05-14")
