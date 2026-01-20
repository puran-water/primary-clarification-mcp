#!/usr/bin/env python3
"""Test PHREEQC alkalinity handling"""

import logging
logging.basicConfig(level=logging.WARNING)

from phreeqpython import PhreeqPython

pp = PhreeqPython(database="phreeqc.dat")

# Test 1: Solution with no metals
print("\n[TEST 1] Solution with no metals")
print("-"*60)
sol1 = pp.add_solution({
    "units": "mg/L",
    "temp": 20,
    "pH": 7.2,
    "Alkalinity": 150,  # as CaCO3
    "Ca": 40,
    "Mg": 15,
    "Na": 50,
    "Cl": 50,
    "S(6)": 30 * 32.06 / 96.06  # Convert SO4 to S
})

alk_mmol = sol1.total("Alkalinity", units='mmol')
alk_caco3 = alk_mmol * 50.04
print(f"pH: {sol1.pH:.2f}")
print(f"Alkalinity: {alk_mmol:.3f} mmol/L = {alk_caco3:.1f} mg/L as CaCO3")
print(f"Ionic strength: {sol1.I:.4f} M")

# Test 2: Same solution with 5 mg/L Al
print("\n[TEST 2] Solution with 5 mg/L Al")
print("-"*60)
sol2 = pp.add_solution({
    "units": "mg/L",
    "temp": 20,
    "pH": 7.2,
    "Alkalinity": 150,
    "Ca": 40,
    "Mg": 15,
    "Na": 50,
    "Cl": 50,
    "S(6)": (30 + 5*5.343) * 32.06 / 96.06,  # Base SO4 + from Al2(SO4)3
    "Al": 5.0
})

alk_mmol2 = sol2.total("Alkalinity", units='mmol')
alk_caco3_2 = alk_mmol2 * 50.04
print(f"pH: {sol2.pH:.2f}")
print(f"Alkalinity: {alk_mmol2:.3f} mmol/L = {alk_caco3_2:.1f} mg/L as CaCO3")
print(f"Alkalinity consumed: {(alk_mmol - alk_mmol2):.3f} mmol/L")
print(f"Ionic strength: {sol2.I:.4f} M")
print(f"Al dissolved: {sol2.total('Al', units='mg'):.2f} mg/L")

# Check if Gibbsite precipitated
try:
    si_gibbsite = sol2.si("Gibbsite")
    print(f"Gibbsite SI: {si_gibbsite:.2f} (SI>0 means oversaturated)")
except:
    print("Gibbsite SI: N/A")

print("\n" + "="*60)
