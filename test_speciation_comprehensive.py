#!/usr/bin/env python3
"""
Comprehensive test of PHREEQC metal speciation module.
Tests multiple scenarios to validate chemistry.
"""

import logging
logging.basicConfig(level=logging.WARNING)

from utils.chemical_speciation import metal_speciation, check_alkalinity_feasibility

print("\n" + "="*70)
print("COMPREHENSIVE PHREEQC SPECIATION TESTS")
print("="*70)

# Test 1: Low alum dose (should not deplete alkalinity)
print("\n[TEST 1] Low Alum Dose (5 mg/L Al)")
print("-"*70)
result1 = metal_speciation(
    dose_al_mg_l=5.0,
    influent_tp_mg_l=5.0,
    ph_in=7.2,
    alkalinity_mg_l_caco3=150
)
print(f"pH: {result1['ph_out']:.2f} (target: ~7.0-7.2)")
print(f"Alkalinity remaining: {result1['alkalinity_out_mg_l_caco3']:.1f} mg/L CaCO3")
print(f"Alkalinity consumed: {result1['alkalinity_consumed_meq_l']:.2f} meq/L")
print(f"Al(OH)3 precipitated: {result1['al_precipitated_mg_l']:.1f} mg/L")
print(f"P removed: {result1['p_precipitated_mg_l']:.2f} mg/L ({result1['p_precipitated_mg_l']/5.0*100:.0f}%)")
print(f"Ionic strength: {result1['ionic_strength_mol_l']:.4f} M")

# Test 2: Medium alum dose (original test)
print("\n[TEST 2] Medium Alum Dose (15 mg/L Al)")
print("-"*70)
result2 = metal_speciation(
    dose_al_mg_l=15.0,
    influent_tp_mg_l=5.0,
    ph_in=7.2,
    alkalinity_mg_l_caco3=150
)
print(f"pH: {result2['ph_out']:.2f}")
print(f"Alkalinity remaining: {result2['alkalinity_out_mg_l_caco3']:.1f} mg/L CaCO3")
print(f"Alkalinity consumed: {result2['alkalinity_consumed_meq_l']:.2f} meq/L")
print(f"Al(OH)3 precipitated: {result2['al_precipitated_mg_l']:.1f} mg/L")
print(f"P removed: {result2['p_precipitated_mg_l']:.2f} mg/L ({result2['p_precipitated_mg_l']/5.0*100:.0f}%)")

# Test 3: Ferric chloride
print("\n[TEST 3] Ferric Chloride (20 mg/L Fe)")
print("-"*70)
result3 = metal_speciation(
    dose_fe_mg_l=20.0,
    influent_tp_mg_l=5.0,
    ph_in=7.2,
    alkalinity_mg_l_caco3=150
)
print(f"pH: {result3['ph_out']:.2f} (target: ~6.8-7.1)")
print(f"Alkalinity remaining: {result3['alkalinity_out_mg_l_caco3']:.1f} mg/L CaCO3")
print(f"Alkalinity consumed: {result3['alkalinity_consumed_meq_l']:.2f} meq/L")
print(f"Fe(OH)3 precipitated: {result3['fe_precipitated_mg_l']:.1f} mg/L")
print(f"P removed: {result3['p_precipitated_mg_l']:.2f} mg/L ({result3['p_precipitated_mg_l']/5.0*100:.0f}%)")
print(f"Minerals formed: {result3['minerals_formed']}")

# Test 4: Low alkalinity warning
print("\n[TEST 4] Alkalinity Feasibility Check")
print("-"*70)
check = check_alkalinity_feasibility(
    dose_fe_mg_l=0.0,
    dose_al_mg_l=30.0,
    alkalinity_mg_l_caco3=80.0
)
print(f"Feasible: {check['feasible']}")
print(f"Alkalinity required: {check['alkalinity_required_mg_l']:.0f} mg/L CaCO3")
print(f"Alkalinity margin: {check['alkalinity_margin_mg_l']:.0f} mg/L")
if check['warning']:
    print(f"Warning: {check['warning']}")

# Test 5: Ionic strength for DLVO
print("\n[TEST 5] Ionic Strength for Different Doses (for DLVO calculations)")
print("-"*70)
doses = [0, 5, 10, 20, 30]
print("Al dose (mg/L) | Ionic Strength (M) | pH      | Status")
print("-"*65)
for dose in doses:
    try:
        result = metal_speciation(
            dose_al_mg_l=dose,
            influent_tp_mg_l=5.0,
            ph_in=7.2,
            alkalinity_mg_l_caco3=150
        )
        print(f"{dose:14.0f} | {result['ionic_strength_mol_l']:19.4f} | {result['ph_out']:7.2f} | OK")
    except ValueError as e:
        print(f"{dose:14.0f} | {'N/A':19s} | {'N/A':7s} | FAIL (alk depleted)")

print("\n" + "="*70)
print("[SUCCESS] All tests completed")
print("="*70)
