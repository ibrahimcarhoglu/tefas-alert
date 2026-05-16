import pytefas
import pandas as pd

try:
    print("Testing pytefas...")
    # pytefas usually has a way to get all funds
    # Let's try to see available functions
    print(dir(pytefas))
    
    # Common usage in pytefas
    # client = pytefas.TefasClient()
    # df = client.get_funds()
    
except Exception as e:
    print(f"Error: {e}")
