import inspect

from mftool import Mftool

mf = Mftool()

def inspect_method(method_name):
    print(f"\n{'='*20} {method_name} {'='*20}")
    method = getattr(mf, method_name)
    try:
        print(f"Signature: {inspect.signature(method)}")
    except Exception as e:
        print(f"Could not get signature: {e}")
    
    try:
        # Some libraries might not provide source if compiled, but let's try
        print("Source Code:")
        print(inspect.getsource(method))
    except Exception as e:
        print(f"Could not get source: {e}")

methods_to_inspect = [
    "get_open_ended_equity_scheme_performance",
    "get_open_ended_debt_scheme_performance",
    "get_open_ended_hybrid_scheme_performance",
    "calculate_returns"
]

for m in methods_to_inspect:
    inspect_method(m)
