#!/usr/bin/env python3
"""Debug alkalinity in PHREEQC"""

from phreeqpython import PhreeqPython

pp = PhreeqPython(database="phreeqc.dat")

# Try different ways to specify alkalinity
sol = pp.add_solution({
    "units": "mg/L",
    "pH": 7.2,
    "Alkalinity": 150,  # Should be as CaCO3 by default
    "Ca": 40,
    "Cl": 71
})

print("Checking what's in the solution:")
print(f"pH: {sol.pH:.2f}")
print(f"Ionic strength: {sol.I:.4f} M")

# Try different ways to get alkalinity
print("\nTrying to get alkalinity:")
try:
    alk1 = sol.total("Alkalinity", units='mmol')
    print(f"  sol.total('Alkalinity', 'mmol'): {alk1:.3f} mmol/L")
except Exception as e:
    print(f"  sol.total('Alkalinity'): ERROR - {e}")

try:
    alk2 = sol.total("Alk", units='mmol')
    print(f"  sol.total('Alk', 'mmol'): {alk2:.3f} mmol/L")
except Exception as e:
    print(f"  sol.total('Alk'): ERROR - {e}")

try:
    c_total = sol.total("C", units='mmol')
    print(f"  sol.total('C', 'mmol'): {c_total:.3f} mmol/L (total carbon)")
except Exception as e:
    print(f"  sol.total('C'): ERROR - {e}")

try:
    c4_total = sol.total("C(4)", units='mmol')
    print(f"  sol.total('C(4)', 'mmol'): {c4_total:.3f} mmol/L (carbonate carbon)")
except Exception as e:
    print(f"  sol.total('C(4)'): ERROR - {e}")

print("\nAll species:")
for species, molality in sol.species.items():
    if molality > 1e-6:  # Only show significant species
        print(f"  {species}: {molality:.6f} mol/kgw")
