from pytefas import Crawler
import inspect

c = Crawler()
print("fetch signature:", inspect.signature(c.fetch))
print("fetch_many signature:", inspect.signature(c.fetch_many))
