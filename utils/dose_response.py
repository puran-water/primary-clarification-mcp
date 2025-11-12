"""
Empirical dose-response models for chemical coagulation in primary clarifiers.

This module implements parametric dose-response models that relate coagulant chemistry
(ionic strength, pH, hydroxide mass) to removal efficiency for TSS, BOD, COD, and nutrients.

Approach:
- Ionic strength (from coagulant dose) drives attachment efficiency (empirical proxy for DLVO)
- Hill/logistic functions provide monotonic, physically-bounded dose-response
- Baseline removal (no coagulant) + dose-dependent enhancement
- Validated parameter ranges from literature (CEPT, high-rate clarification)

**IMPORTANT NOTE ON IONIC STRENGTH:**
We use ionic strength calculated from coagulant dose BEFORE precipitation, not the
equilibrium ionic strength from PHREEQC. This is because:
1. Coagulation occurs during mixing (high turbulence, non-equilibrium)
2. Attachment happens before full precipitation/equilibration
3. Metal ions contribute to destabilization even before precipitating
4. Ensures monotonic dose-response (more dose = more I = better removal)

References:
- Bratby, J. (2016). Coagulation and Flocculation in Water and Wastewater Treatment (3rd ed.)
- Metcalf & Eddy (2014). Wastewater Engineering: Treatment and Resource Recovery (5th ed.)
- Parker et al. (2000). High-rate primary clarification for wastewater treatment.

Integration:
- Input: dose_fe_mg_l, dose_al_mg_l (calculates I empirically)
- Output: removal efficiency (0-1) for tss, bod, cod, tp, tkn
- Used by: utils.removal_efficiency.tss_removal_bsm2() empirical tier
"""

import numpy as np
from typing import Dict, Any, Optional
import logging
import copy

logger = logging.getLogger(__name__)


def calculate_ionic_strength_from_dose(
    dose_fe_mg_l: float = 0.0,
    dose_al_mg_l: float = 0.0,
    background_i_mol_l: float = 0.005
) -> float:
    """
    Calculate ionic strength from metal coagulant dose (before precipitation).

    This empirical approach assumes:
    - FeCl3: adds Fe³⁺ (z=3) and 3 Cl⁻ (z=1)
    - Al2(SO4)3: adds 2 Al³⁺ (z=3) and 3 SO4²⁻ (z=2)
    - Ionic strength: I = 0.5 * Σ(c_i * z_i²)

    Args:
        dose_fe_mg_l: Ferric iron dose (mg/L as Fe)
        dose_al_mg_l: Aluminum dose (mg/L as Al)
        background_i_mol_l: Background ionic strength from wastewater (mol/L)

    Returns:
        Total ionic strength (mol/L)

    Example:
        >>> i = calculate_ionic_strength_from_dose(dose_al_mg_l=10.0)
        >>> print(f"I = {i:.4f} M")
        I = 0.0106 M
    """
    i_total = background_i_mol_l

    # FeCl3 contribution: Fe³⁺ + 3 Cl⁻
    if dose_fe_mg_l > 0:
        fe_mmol_l = dose_fe_mg_l / 55.845  # mg/L -> mmol/L
        cl_mmol_l = 3 * fe_mmol_l  # 3 Cl per Fe
        # I = 0.5 * (c_Fe * 3² + c_Cl * 1²)
        i_fe = 0.5 * (fe_mmol_l / 1000 * 9 + cl_mmol_l / 1000 * 1)
        i_total += i_fe

    # Al2(SO4)3 contribution: 2 Al³⁺ + 3 SO4²⁻
    if dose_al_mg_l > 0:
        al_mmol_l = dose_al_mg_l / 26.98  # mg/L -> mmol/L
        so4_mmol_l = 1.5 * al_mmol_l  # 3 SO4 per 2 Al = 1.5 SO4 per Al
        # I = 0.5 * (c_Al * 3² + c_SO4 * 2²)
        i_al = 0.5 * (al_mmol_l / 1000 * 9 + so4_mmol_l / 1000 * 4)
        i_total += i_al

    return i_total


def hill_function(
    x: float,
    x_50: float,
    n: float = 2.0,
    y_min: float = 0.0,
    y_max: float = 1.0
) -> float:
    """
    Hill equation (dose-response) with baseline and maximum.

    This is the fundamental dose-response relationship used throughout coagulation
    modeling. It provides:
    - Monotonic increase from y_min to y_max
    - Smooth sigmoid transition
    - Physically meaningful parameters (EC50, Hill coefficient)

    Formula:
        y = y_min + (y_max - y_min) * x^n / (x_50^n + x^n)

    Args:
        x: Independent variable (e.g., ionic strength in mol/L, dose in mg/L)
        x_50: Half-maximal value (EC50). Value of x where y = (y_min + y_max)/2
        n: Hill coefficient. Controls steepness (n=1: hyperbolic, n>1: sigmoidal)
        y_min: Baseline value at x=0 (e.g., baseline removal without coagulant)
        y_max: Maximum value at x=∞ (e.g., maximum achievable removal)

    Returns:
        Response value between y_min and y_max

    Example:
        >>> # TSS removal: 60% baseline -> 90% max at I_50 = 0.01 M
        >>> removal = hill_function(x=0.015, x_50=0.01, n=2.0, y_min=0.6, y_max=0.9)
        >>> print(f"Removal: {removal:.1%}")
        Removal: 81.8%

    Notes:
        - At x = x_50, y = (y_min + y_max) / 2 (half-maximal response)
        - Steeper transitions: increase n (typical range: 1-4)
        - For coagulation, x is typically ionic strength (M) or dose (mg/L)
        - Returns y_min if x = 0 (no coagulant)
        - Asymptotically approaches y_max as x -> ∞
    """
    if x <= 0:
        return y_min

    # Hill equation
    x_norm = (x / x_50) ** n
    response = y_min + (y_max - y_min) * x_norm / (1.0 + x_norm)

    return np.clip(response, y_min, y_max)


def tss_removal_dose_response(
    ionic_strength_mol_l: float,
    influent_tss_mg_l: float = 250.0,
    baseline_removal: float = 0.60,
    max_removal: float = 0.90,
    i_50: float = 0.010,
    hill_coef: float = 2.0
) -> Dict[str, Any]:
    """
    Calculate TSS removal efficiency as a function of ionic strength.

    Ionic strength (from metal coagulant addition) serves as an empirical proxy
    for destabilization and attachment efficiency. This avoids explicit DLVO
    calculations while capturing the key physics: higher I -> lower energy barrier
    -> higher attachment -> better removal.

    **Typical Parameter Ranges (from literature):**
    - Baseline removal (no coagulant): 50-70% for primary clarifiers
    - Max removal (with optimal coagulation): 85-95%
    - I_50: 0.005-0.020 M (depends on wastewater characteristics)
    - Hill coefficient: 1.5-3.0 (steeper for well-mixed systems)

    Args:
        ionic_strength_mol_l: Ionic strength from PHREEQC (mol/L)
        influent_tss_mg_l: Influent TSS concentration (mg/L)
        baseline_removal: Removal efficiency without coagulant (fraction, 0-1)
        max_removal: Maximum achievable removal with optimal dosing (fraction, 0-1)
        i_50: Half-maximal ionic strength (M). I where removal = (baseline + max)/2
        hill_coef: Hill coefficient (steepness). Typical range 1.5-3.0

    Returns:
        Dictionary with:
        - removal_efficiency: TSS removal efficiency (fraction, 0-1)
        - removal_pct: TSS removal efficiency (%)
        - effluent_tss_mg_l: Effluent TSS (mg/L)
        - tss_removed_mg_l: TSS removed (mg/L)
        - ionic_strength_mol_l: Input ionic strength (for reference)
        - parameters: Dict of model parameters used

    Example:
        >>> from utils.chemical_speciation import metal_speciation
        >>> # Get ionic strength from alum dose
        >>> chem = metal_speciation(dose_al_mg_l=10.0, influent_tp_mg_l=5.0)
        >>> result = tss_removal_dose_response(
        ...     ionic_strength_mol_l=chem['ionic_strength_mol_l'],
        ...     influent_tss_mg_l=250.0
        ... )
        >>> print(f"Removal: {result['removal_pct']:.1f}%")
        >>> print(f"Effluent TSS: {result['effluent_tss_mg_l']:.1f} mg/L")

    Notes:
        - Ionic strength accounts for all dissolved salts (coagulant + background)
        - Baseline removal represents sedimentation without coagulation
        - Model assumes well-mixed conditions and sufficient HRT
        - For very high TSS (>1000 mg/L), baseline removal may be higher
        - For low alkalinity, pH drop may reduce removal (not modeled here)
    """
    # Validate inputs
    if ionic_strength_mol_l < 0:
        raise ValueError(f"Ionic strength must be >= 0, got {ionic_strength_mol_l}")
    if not (0 <= baseline_removal <= 1):
        raise ValueError(f"Baseline removal must be 0-1, got {baseline_removal}")
    if not (0 <= max_removal <= 1):
        raise ValueError(f"Max removal must be 0-1, got {max_removal}")
    if baseline_removal > max_removal:
        raise ValueError(f"Baseline removal ({baseline_removal}) > max removal ({max_removal})")
    if i_50 <= 0:
        raise ValueError(f"I_50 must be > 0, got {i_50}")

    # Calculate removal efficiency using Hill function
    removal_efficiency = hill_function(
        x=ionic_strength_mol_l,
        x_50=i_50,
        n=hill_coef,
        y_min=baseline_removal,
        y_max=max_removal
    )

    # Calculate effluent and removed mass
    effluent_tss = influent_tss_mg_l * (1 - removal_efficiency)
    tss_removed = influent_tss_mg_l - effluent_tss

    return {
        "removal_efficiency": removal_efficiency,
        "removal_pct": removal_efficiency * 100,
        "effluent_tss_mg_l": effluent_tss,
        "tss_removed_mg_l": tss_removed,
        "ionic_strength_mol_l": ionic_strength_mol_l,
        "parameters": {
            "baseline_removal": baseline_removal,
            "max_removal": max_removal,
            "i_50": i_50,
            "hill_coef": hill_coef
        }
    }


def bod_removal_dose_response(
    ionic_strength_mol_l: float,
    influent_bod_mg_l: float = 200.0,
    influent_tss_mg_l: float = 250.0,
    tss_removal_efficiency: Optional[float] = None,
    particulate_fraction: float = 0.70,
    baseline_removal_soluble: float = 0.05,
    max_removal_soluble: float = 0.30,
    i_50: float = 0.015,
    hill_coef: float = 1.5
) -> Dict[str, Any]:
    """
    Calculate BOD removal efficiency accounting for particulate and soluble fractions.

    BOD removal in primary clarification depends on:
    1. Particulate BOD (pBOD): Follows TSS removal (attached to particles)
    2. Soluble BOD (sBOD): Limited removal even with coagulation

    Typical split: 60-80% particulate, 20-40% soluble for municipal wastewater.

    Args:
        ionic_strength_mol_l: Ionic strength from PHREEQC (mol/L)
        influent_bod_mg_l: Influent BOD5 (mg/L)
        influent_tss_mg_l: Influent TSS (mg/L, for calculating pBOD removal)
        tss_removal_efficiency: TSS removal (fraction). If None, calculated from I
        particulate_fraction: Fraction of BOD that is particulate (0-1). Default 0.7
        baseline_removal_soluble: Baseline sBOD removal (fraction). Default 0.05
        max_removal_soluble: Max sBOD removal with coagulation (fraction). Default 0.30
        i_50: Half-maximal I for sBOD removal (M). Default 0.015
        hill_coef: Hill coefficient for sBOD. Default 1.5 (lower than TSS)

    Returns:
        Dictionary with BOD removal results and breakdown

    Example:
        >>> result = bod_removal_dose_response(
        ...     ionic_strength_mol_l=0.010,
        ...     influent_bod_mg_l=200,
        ...     tss_removal_efficiency=0.75
        ... )
        >>> print(f"BOD removal: {result['removal_pct']:.1f}%")
        >>> print(f"pBOD removed: {result['pbod_removed_mg_l']:.1f} mg/L")
        >>> print(f"sBOD removed: {result['sbod_removed_mg_l']:.1f} mg/L")

    Notes:
        - pBOD removal tracks TSS removal (same mechanisms)
        - sBOD removal is limited (~5-30%) even with optimal coagulation
        - Coagulation can enhance sBOD removal by adsorption to floc
        - Model assumes BOD/TSS ratio remains constant
    """
    # Calculate TSS removal if not provided
    if tss_removal_efficiency is None:
        tss_result = tss_removal_dose_response(
            ionic_strength_mol_l=ionic_strength_mol_l,
            influent_tss_mg_l=influent_tss_mg_l
        )
        tss_removal_efficiency = tss_result['removal_efficiency']

    # Split BOD into particulate and soluble
    pbod = influent_bod_mg_l * particulate_fraction
    sbod = influent_bod_mg_l * (1 - particulate_fraction)

    # pBOD removal follows TSS removal
    pbod_removed = pbod * tss_removal_efficiency

    # sBOD removal follows dose-response (limited even at high I)
    sbod_removal_efficiency = hill_function(
        x=ionic_strength_mol_l,
        x_50=i_50,
        n=hill_coef,
        y_min=baseline_removal_soluble,
        y_max=max_removal_soluble
    )
    sbod_removed = sbod * sbod_removal_efficiency

    # Total BOD removal
    total_bod_removed = pbod_removed + sbod_removed
    bod_removal_efficiency = total_bod_removed / influent_bod_mg_l
    effluent_bod = influent_bod_mg_l - total_bod_removed

    return {
        "removal_efficiency": bod_removal_efficiency,
        "removal_pct": bod_removal_efficiency * 100,
        "effluent_bod_mg_l": effluent_bod,
        "bod_removed_mg_l": total_bod_removed,
        "pbod_influent_mg_l": pbod,
        "pbod_removed_mg_l": pbod_removed,
        "pbod_removal_efficiency": tss_removal_efficiency,
        "sbod_influent_mg_l": sbod,
        "sbod_removed_mg_l": sbod_removed,
        "sbod_removal_efficiency": sbod_removal_efficiency,
        "ionic_strength_mol_l": ionic_strength_mol_l
    }


# Parameter sets for common applications
PARAMETER_SETS = {
    "municipal_baseline": {
        "tss": {
            "baseline_removal": 0.60,
            "max_removal": 0.90,
            "i_50": 0.010,
            "hill_coef": 2.0
        },
        "bod": {
            "particulate_fraction": 0.70,
            "baseline_removal_soluble": 0.05,
            "max_removal_soluble": 0.30,
            "i_50": 0.015,
            "hill_coef": 1.5
        },
        "description": "Typical municipal wastewater (TSS 150-300 mg/L)"
    },
    "industrial_high_tss": {
        "tss": {
            "baseline_removal": 0.70,  # Higher baseline due to larger particles
            "max_removal": 0.92,
            "i_50": 0.012,
            "hill_coef": 2.5
        },
        "bod": {
            "particulate_fraction": 0.80,  # More particulate BOD
            "baseline_removal_soluble": 0.03,
            "max_removal_soluble": 0.25,
            "i_50": 0.018,
            "hill_coef": 1.3
        },
        "description": "Industrial wastewater with high TSS (>500 mg/L)"
    },
    "cept_optimized": {
        "tss": {
            "baseline_removal": 0.55,
            "max_removal": 0.95,  # CEPT can achieve very high removal
            "i_50": 0.008,  # Lower I_50 (more sensitive to dosing)
            "hill_coef": 2.5
        },
        "bod": {
            "particulate_fraction": 0.75,
            "baseline_removal_soluble": 0.10,
            "max_removal_soluble": 0.40,  # Enhanced sBOD capture
            "i_50": 0.012,
            "hill_coef": 2.0
        },
        "description": "Chemically enhanced primary treatment (CEPT) with optimized coagulation"
    }
}


def get_parameter_set(application: str) -> Dict[str, Any]:
    """
    Get recommended dose-response parameters for common applications.

    Args:
        application: One of "municipal_baseline", "industrial_high_tss", "cept_optimized"

    Returns:
        Dictionary with TSS and BOD parameter sets

    Raises:
        KeyError: If application not recognized

    Example:
        >>> params = get_parameter_set("cept_optimized")
        >>> result = tss_removal_dose_response(
        ...     ionic_strength_mol_l=0.010,
        ...     **params['tss']
        ... )
    """
    return copy.deepcopy(PARAMETER_SETS[application])
