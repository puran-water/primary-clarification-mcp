#!/usr/bin/env python3
"""Quick test to understand calc_f_i signature"""

import logging
logging.basicConfig(level=logging.ERROR)

try:
    from qsdsan.sanunits._clarifier import calc_f_i
    import inspect

    print("calc_f_i signature:")
    print(inspect.signature(calc_f_i))
    print()

    # Try with different argument combinations
    print("Testing calc_f_i with 3 args:")
    try:
        result = calc_f_i(0.10, 1.0, 0.03)  # X_I, temp_correction, X_underflow
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    print("\nTrying with help:")
    help(calc_f_i)

except ImportError as e:
    print(f"Import error: {e}")
