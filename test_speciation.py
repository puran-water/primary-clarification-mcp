#!/usr/bin/env python3
"""
Quick test of PHREEQC metal speciation module.
"""

import logging
logging.basicConfig(level=logging.DEBUG)

from utils.chemical_speciation import metal_speciation

# Test case: Alum dose for CEPT (Chemically Enhanced Primary Treatment)
print("\n" + "="*70)
print("TEST: Alum dose for CEPT")
print("="*70)

result = metal_speciation(
    dose_al_mg_l=15.0,  # mg/L as Al (≈100 mg/L as Al2(SO4)3)
    influent_tp_mg_l=5.0,
    ph_in=7.2,
    alkalinity_mg_l_caco3=150
)

print(f"\n[SUCCESS] PHREEQC Speciation Results:")
print(f"   pH: 7.2 -> {result['ph_out']:.2f}")
print(f"   Alkalinity consumed: {result['alkalinity_consumed_meq_l']:.2f} meq/L")
print(f"   Al(OH)3 precipitated: {result['al_precipitated_mg_l']:.1f} mg/L")
print(f"   P precipitated: {result['p_precipitated_mg_l']:.2f} mg/L")
print(f"   P effluent: {result['p_effluent_mg_l']:.2f} mg/L")
print(f"   Ionic strength: {result['ionic_strength_mol_l']:.4f} M")
print(f"   Minerals formed: {result['minerals_formed']}")
print(f"\nFull result:")
for key, val in result.items():
    print(f"   {key}: {val}")

print("\n[SUCCESS] Database loading successful!")
print("="*70)
