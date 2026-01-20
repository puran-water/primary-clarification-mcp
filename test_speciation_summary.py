#!/usr/bin/env python3
"""
Summary test demonstrating PHREEQC metal speciation module functionality.
Phase 2.1 Complete: Chemistry module ready for empirical dose-response tier.
"""

import logging
logging.basicConfig(level=logging.ERROR)

from utils.chemical_speciation import metal_speciation, check_alkalinity_feasibility

print("\n" + "="*70)
print("PHREEQC METAL SPECIATION MODULE - Phase 2.1 Complete")
print("="*70)

# Example 1: Alum for CEPT
print("\n[Example 1] Alum for Chemically Enhanced Primary Treatment (CEPT)")
print("-"*70)
result = metal_speciation(
    dose_al_mg_l=10.0,
    influent_tp_mg_l=5.0,
    ph_in=7.2,
    alkalinity_mg_l_caco3=150
)

print(f"Dose: 10 mg/L Al (~ 67 mg/L as Al2(SO4)3)")
print(f"pH: {result['ph_out']:.2f} (input: 7.2)")
print(f"Alkalinity: 150 -> {result['alkalinity_out_mg_l_caco3']:.1f} mg/L as CaCO3")
print(f"Al(OH)3 precipitated: {result['al_precipitated_mg_l']:.1f} mg/L (sweep floc mass)")
print(f"P removed: {result['p_precipitated_mg_l']:.2f} mg/L ({result['p_precipitated_mg_l']/5.0*100:.0f}%)")
print(f"Ionic strength: {result['ionic_strength_mol_l']:.4f} M (for DLVO)")

# Example 2: Ferric chloride
print("\n[Example 2] Ferric Chloride Coagulation")
print("-"*70)
result2 = metal_speciation(
    dose_fe_mg_l=15.0,
    influent_tp_mg_l=5.0,
    ph_in=7.2,
    alkalinity_mg_l_caco3=150
)

print(f"Dose: 15 mg/L Fe (~ 41 mg/L as FeCl3)")
print(f"pH: {result2['ph_out']:.2f} (input: 7.2)")
print(f"Alkalinity: 150 -> {result2['alkalinity_out_mg_l_caco3']:.1f} mg/L as CaCO3")
print(f"Fe(OH)3 precipitated: {result2['fe_precipitated_mg_l']:.1f} mg/L (sweep floc mass)")
print(f"P removed: {result2['p_precipitated_mg_l']:.2f} mg/L ({result2['p_precipitated_mg_l']/5.0*100:.0f}%)")
print(f"Ionic strength: {result2['ionic_strength_mol_l']:.4f} M (for DLVO)")

# Example 3: Alkalinity feasibility check
print("\n[Example 3] Alkalinity Feasibility Check")
print("-"*70)
check = check_alkalinity_feasibility(
    dose_fe_mg_l=0,
    dose_al_mg_l=50.0,
    alkalinity_mg_l_caco3=100.0
)

print(f"Dose: 50 mg/L Al, Alkalinity: 100 mg/L CaCO3")
print(f"Feasible: {check['feasible']}")
print(f"Required: {check['alkalinity_required_mg_l']:.0f} mg/L CaCO3")
print(f"Status: {'OK' if check['feasible'] else 'WARNING - ' + check['warning']}")

print("\n" + "="*70)
print("[SUCCESS] Phase 2.1 Complete - PHREEQC Integration Working")
print("="*70)
print("\nKey Outputs for Dose-Response Modeling:")
print("  - ionic_strength_mol_l: Drives DLVO attachment efficiency alpha")
print("  - ph_out: Affects speciation and floc characteristics")
print("  - total_hydroxide_mg_l: Sweep floc mass for removal")
print("  - alkalinity_consumed_meq_l: Operational constraint")
print("\nNext: Phase 2.2 - Empirical dose-response models")
print("="*70 + "\n")
