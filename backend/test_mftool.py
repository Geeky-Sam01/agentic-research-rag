import time

from app.services.mf_instance import mf

start = time.time()
print("Fetching quote...")
try:
    quote = mf.get_scheme_quote("122639", as_json=False)
    print("Quote:", quote)
except Exception as e:
    print("Error:", e)
print(f"Time taken: {time.time() - start:.2f} seconds")
