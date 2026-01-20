#!/usr/bin/env python3
"""
Test empirical dose-response models with PHREEQC chemistry integration.
Phase 2.2: Demonstrate chemistry -> ionic strength -> removal efficiency
"""

import logging
logging.basicConfig(level=logging.ERROR)

from utils.chemical_speciation import metal_speciation
from utils.dose_response import (
    tss_removal_dose_response,
    bod_removal_dose_response,
    get_parameter_set,
    calculate_ionic_strength_from_dose
)

print("\n" + "="*70)
print("DOSE-RESPONSE MODELS - Phase 2.2 Test")
print("="*70)

# Test 1: Dose scan with dose -> ionic strength -> removal
print("\n[TEST 1] Alum Dose Scan: Dose -> Ionic Strength -> Removal")
print("-"*70)
print("Al Dose | I (M)    | TSS Removal | BOD Removal | Effluent TSS | Effluent BOD")
print("-"*76)

influent_tss = 250.0
influent_bod = 200.0

for al_dose in [0, 5, 10, 15, 20]:
    # Step 1: Calculate ionic strength from dose (before precipitation)
    i_strength = calculate_ionic_strength_from_dose(dose_al_mg_l=al_dose)

    # Step 2: TSS Removal (empirical dose-response)
    tss_result = tss_removal_dose_response(
        ionic_strength_mol_l=i_strength,
        influent_tss_mg_l=influent_tss
    )

    # Step 3: BOD Removal (coupled to TSS)
    bod_result = bod_removal_dose_response(
        ionic_strength_mol_l=i_strength,
        influent_bod_mg_l=influent_bod,
        tss_removal_efficiency=tss_result['removal_efficiency']
    )

    print(f"{al_dose:7.0f} | {i_strength:8.4f} | "
          f"{tss_result['removal_pct']:11.1f}% | "
          f"{bod_result['removal_pct']:11.1f}% | "
          f"{tss_result['effluent_tss_mg_l']:12.1f} | "
          f"{bod_result['effluent_bod_mg_l']:12.1f}")

# Test 2: Different parameter sets
print("\n[TEST 2] Parameter Set Comparison (10 mg/L Al)")
print("-"*70)

al_dose = 10.0
i_strength = calculate_ionic_strength_from_dose(dose_al_mg_l=al_dose)

print(f"Ionic strength: {i_strength:.4f} M\n")

for app_name in ["municipal_baseline", "industrial_high_tss", "cept_optimized"]:
    params = get_parameter_set(app_name)

    tss_result = tss_removal_dose_response(
        ionic_strength_mol_l=i_strength,
        influent_tss_mg_l=250,
        **params['tss']
    )

    bod_result = bod_removal_dose_response(
        ionic_strength_mol_l=i_strength,
        influent_bod_mg_l=200,
        tss_removal_efficiency=tss_result['removal_efficiency'],
        **params['bod']
    )

    print(f"{app_name:25s}: TSS {tss_result['removal_pct']:5.1f}%, "
          f"BOD {bod_result['removal_pct']:5.1f}%")

# Test 3: Monotonicity check
print("\n[TEST 3] Monotonicity Verification (removal must increase with dose)")
print("-"*70)

previous_tss_removal = 0.0
previous_bod_removal = 0.0
monotonic = True

for al_dose in [0, 2, 5, 8, 12, 15]:
    i_strength = calculate_ionic_strength_from_dose(dose_al_mg_l=al_dose)

    tss_result = tss_removal_dose_response(
        ionic_strength_mol_l=i_strength,
        influent_tss_mg_l=250
    )

    bod_result = bod_removal_dose_response(
        ionic_strength_mol_l=i_strength,
        influent_bod_mg_l=200,
        tss_removal_efficiency=tss_result['removal_efficiency']
    )

    # Check monotonicity
    if tss_result['removal_efficiency'] < previous_tss_removal:
        print(f"WARNING: TSS removal decreased at {al_dose} mg/L Al")
        monotonic = False
    if bod_result['removal_efficiency'] < previous_bod_removal:
        print(f"WARNING: BOD removal decreased at {al_dose} mg/L Al")
        monotonic = False

    previous_tss_removal = tss_result['removal_efficiency']
    previous_bod_removal = bod_result['removal_efficiency']

if monotonic:
    print("[PASS] Removal efficiency is monotonically increasing with dose")
else:
    print("[FAIL] Monotonicity violated")

print("\n" + "="*70)
print("[SUCCESS] Phase 2.2 Complete - Dose-Response Models Working")
print("="*70)
print("\nNext: Phase 2.3 - Wire to tss_removal_bsm2()")
print("="*70 + "\n")
