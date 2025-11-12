"""
Chemical speciation module for coagulation chemistry using PHREEQC.

This module provides lightweight wrappers around phreeqpython for computing
metal speciation, precipitation, pH effects, and alkalinity consumption when
adding Fe/Al coagulants to wastewater.

Approach adapted from water-chemistry-mcp's validated PHREEQC integration.

Key outputs for dose-responsive removal models:
- pH shift (alkalinity consumption)
- Precipitated metal hydroxide mass (sweep floc)
- Ionic strength (for DLVO attachment efficiency)
- Dissolved metal charge (for charge neutralization)
- Phosphorus precipitation (stoichiometric floor)

References:
- Parkhurst, D.L., & Appelo, C.A.J. (2013). PHREEQC Version 3.
- water-chemistry-mcp: ../water-chemistry-mcp (database detection pattern)
"""

import logging
import os
from typing import Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)

# Import phreeqpython with fail-loud behavior
try:
    from phreeqpython import PhreeqPython
except ImportError as e:
    raise ImportError(
        f"Failed to import phreeqpython: {e}\n\n"
        "This is a CRITICAL ERROR. PHREEQC is required for chemical speciation.\n"
        "Install with: pip install phreeqpython\n"
        "DO NOT add fallback logic. Fix the dependency issue."
    ) from e

# Find PHREEQC database (borrow water-chemistry-mcp approach)
def get_default_database():
    """Find PHREEQC database file."""
    PHREEQC_DATABASE_PATHS = [
        r"C:\Program Files\USGS\phreeqc-3.8.6-17100-x64\database\phreeqc.dat",  # Windows
        r"/mnt/c/Program Files/USGS/phreeqc-3.8.6-17100-x64/database/phreeqc.dat",  # WSL
        r"/usr/local/share/phreeqc/database/phreeqc.dat",  # Linux
        r"/opt/phreeqc/database/phreeqc.dat",  # Docker
    ]

    for db_path in PHREEQC_DATABASE_PATHS:
        if os.path.exists(db_path):
            logger.info(f"Found PHREEQC database: {db_path}")
            return db_path

    # Fallback to phreeqpython bundled database
    try:
        import phreeqpython
        pkg_dir = os.path.dirname(phreeqpython.__file__)

        # Check multiple possible locations
        possible_paths = [
            os.path.join(pkg_dir, 'database', 'phreeqc.dat'),
            os.path.join(pkg_dir, 'databases', 'phreeqc.dat'),
            os.path.join(os.path.dirname(pkg_dir), 'phreeqpython', 'database', 'phreeqc.dat')
        ]

        for bundled_db in possible_paths:
            if os.path.exists(bundled_db):
                logger.info(f"Using phreeqpython bundled database: {bundled_db}")
                return bundled_db

        # Last resort: just return name and let phreeqpython find it
        logger.warning("Could not find explicit database path, using 'phreeqc.dat'")
        return "phreeqc.dat"
    except Exception as e:
        logger.warning(f"Error finding database: {e}")
        return "phreeqc.dat"

DEFAULT_DATABASE = get_default_database()


def _calculate_ionic_strength_from_dose(
    dose_fe_mg_l: float = 0.0,
    dose_al_mg_l: float = 0.0,
    background_i_mol_l: float = 0.005
) -> float:
    """
    Calculate ionic strength from metal coagulant dose (before precipitation).

    Internal helper function - see utils.dose_response.calculate_ionic_strength_from_dose()
    for the public version with full documentation.
    """
    i_total = background_i_mol_l

    # FeCl3 contribution: Fe³⁺ + 3 Cl⁻
    if dose_fe_mg_l > 0:
        fe_mmol_l = dose_fe_mg_l / 55.845
        cl_mmol_l = 3 * fe_mmol_l
        i_fe = 0.5 * (fe_mmol_l / 1000 * 9 + cl_mmol_l / 1000 * 1)
        i_total += i_fe

    # Al2(SO4)3 contribution: 2 Al³⁺ + 3 SO4²⁻
    if dose_al_mg_l > 0:
        al_mmol_l = dose_al_mg_l / 26.98
        so4_mmol_l = 1.5 * al_mmol_l
        i_al = 0.5 * (al_mmol_l / 1000 * 9 + so4_mmol_l / 1000 * 4)
        i_total += i_al

    return i_total


def metal_speciation(
    dose_fe_mg_l: float = 0.0,
    dose_al_mg_l: float = 0.0,
    influent_tp_mg_l: float = 5.0,
    ph_in: float = 7.0,
    alkalinity_mg_l_caco3: float = 100.0,
    temperature_c: float = 20.0,
    ca_mg_l: float = 40.0,
    mg_mg_l: float = 15.0,
    na_mg_l: float = 50.0,
    cl_mg_l: float = 50.0,
    so4_mg_l: float = 30.0
) -> Dict[str, Any]:
    """
    Compute metal speciation and precipitation from Fe/Al coagulant addition.

    Uses PHREEQC to calculate chemical equilibrium, including:
    - pH shift from metal hydrolysis
    - Alkalinity consumption
    - Metal hydroxide precipitation (sweep floc mass)
    - Phosphate precipitation (if P present)
    - Ionic strength
    - Dissolved metal charge

    Args:
        dose_fe_mg_l: Ferric iron dose (mg/L as Fe). Assumes FeCl3 or Fe2(SO4)3 product.
        dose_al_mg_l: Aluminum dose (mg/L as Al). Assumes Al2(SO4)3 product.
        influent_tp_mg_l: Influent total phosphorus (mg/L as P).
        ph_in: Influent pH.
        alkalinity_mg_l_caco3: Alkalinity (mg/L as CaCO3).
        temperature_c: Temperature (°C).
        ca_mg_l: Calcium (mg/L).
        mg_mg_l: Magnesium (mg/L).
        na_mg_l: Sodium (mg/L).
        cl_mg_l: Chloride (mg/L).
        so4_mg_l: Sulfate as SO4 (mg/L).

    Returns:
        Dictionary with:
        - ph_out: Final pH after metal addition
        - alkalinity_out_mg_l_caco3: Residual alkalinity
        - alkalinity_consumed_meq_l: Alkalinity consumed (meq/L)
        - fe_precipitated_mg_l: Ferric hydroxide precipitated (mg/L as Fe(OH)3)
        - al_precipitated_mg_l: Aluminum hydroxide precipitated (mg/L as Al(OH)3)
        - p_precipitated_mg_l: Phosphorus precipitated (mg/L as P)
        - p_effluent_mg_l: Dissolved phosphorus remaining
        - ionic_strength_mol_l: Pre-precipitation ionic strength (mol/L) - use for dose-response
        - ionic_strength_equilibrium_mol_l: Equilibrium ionic strength (mol/L) from PHREEQC
        - fe_dissolved_mg_l: Dissolved Fe (mg/L)
        - al_dissolved_mg_l: Dissolved Al (mg/L)
        - minerals_formed: List of precipitated mineral names

        Note: ionic_strength_mol_l represents the ionic strength during rapid mixing
        (before metal precipitation) and should be used for attachment efficiency/
        dose-response models. ionic_strength_equilibrium_mol_l is the equilibrium
        value after precipitation and is typically lower.

    Example:
        >>> # Alum dose for CEPT
        >>> result = metal_speciation(
        ...     dose_al_mg_l=15.0,  # mg/L as Al (≈100 mg/L as Al2(SO4)3)
        ...     influent_tp_mg_l=5.0,
        ...     ph_in=7.2,
        ...     alkalinity_mg_l_caco3=150
        ... )
        >>> print(f"pH: {result['ph_out']:.2f}")
        >>> print(f"Al(OH)3 precipitated: {result['al_precipitated_mg_l']:.1f} mg/L")
        >>> print(f"P precipitated: {result['p_precipitated_mg_l']:.2f} mg/L")
    """
    # Initialize PHREEQC with robust three-step fallback pattern
    # (borrowed from water-chemistry-mcp for reliability)
    db_basename = os.path.basename(DEFAULT_DATABASE)

    try:
        # Step 1: Try basename (phreeqpython often prefers this)
        pp = PhreeqPython(database=db_basename)
        logger.debug(f"PhreeqPython initialized with basename: {db_basename}")
    except Exception as e:
        logger.warning(f"Could not initialize with basename {db_basename}, trying full path: {e}")
        try:
            # Step 2: Try full path
            pp = PhreeqPython(database=DEFAULT_DATABASE)
            logger.debug(f"PhreeqPython initialized with full path: {DEFAULT_DATABASE}")
        except Exception as e2:
            logger.warning(f"Could not initialize with full path, using load_database: {e2}")
            # Step 3: Create instance then load database manually
            pp = PhreeqPython()
            pp.ip.load_database(DEFAULT_DATABASE)
            logger.debug(f"PhreeqPython database loaded manually: {DEFAULT_DATABASE}")

    # Calculate counter-ions from coagulant salts
    # FeCl3: 3 Cl per Fe → (3 × 35.45) / 55.845 = 1.906 g Cl per g Fe
    # Al2(SO4)3: 3 SO4 per 2 Al → (3 × 96.06) / (2 × 26.98) = 5.343 g SO4 per g Al
    cl_from_fe = dose_fe_mg_l * 1.906 if dose_fe_mg_l > 0 else 0
    so4_from_al = dose_al_mg_l * 5.343 if dose_al_mg_l > 0 else 0

    # Calculate ionic strength from dose (before precipitation) for dose-response models
    # This represents the ionic strength during rapid mixing where destabilization occurs
    ionic_strength_dose = _calculate_ionic_strength_from_dose(
        dose_fe_mg_l=dose_fe_mg_l,
        dose_al_mg_l=dose_al_mg_l,
        background_i_mol_l=(ca_mg_l/40.08 + mg_mg_l/24.31 + na_mg_l/22.99 +
                           cl_mg_l/35.45 + so4_mg_l/96.06) / 1000 * 0.5  # Rough estimate
    )

    # Create influent solution with metals included
    # Note: PHREEQC may fail to converge if alkalinity is insufficient for the metal dose
    solution_def = {
        "units": "mg/L",
        "temp": temperature_c,
        "pH": ph_in,
        "Alkalinity": alkalinity_mg_l_caco3,  # as CaCO3
        "Ca": ca_mg_l,
        "Mg": mg_mg_l,
        "Na": na_mg_l,
        "Cl": cl_mg_l + cl_from_fe,  # Base Cl + Cl from FeCl3
        "S(6)": (so4_mg_l + so4_from_al) * 32.06 / 96.06,  # Convert total SO4 to S
        "P": influent_tp_mg_l  # Total P as PO4
    }

    # Add metals if present (use correct PHREEQC element names)
    if dose_fe_mg_l > 0:
        solution_def["Fe(+3)"] = dose_fe_mg_l  # Ferric iron (PHREEQC standard name)

    if dose_al_mg_l > 0:
        solution_def["Al"] = dose_al_mg_l  # Aluminum

    # Create solution - PHREEQC will compute equilibrium
    # Catch convergence errors due to alkalinity depletion
    try:
        sol = pp.add_solution(solution_def)
    except Exception as e:
        error_msg = str(e)
        if "not converged" in error_msg or "non-carbonate alkalinity" in error_msg:
            # Alkalinity insufficient - return warning
            logger.error(f"PHREEQC convergence failed: {error_msg}")
            raise ValueError(
                f"Insufficient alkalinity for metal dose. "
                f"Dose: Fe={dose_fe_mg_l:.1f} mg/L, Al={dose_al_mg_l:.1f} mg/L. "
                f"Alkalinity: {alkalinity_mg_l_caco3:.0f} mg/L as CaCO3. "
                f"Check alkalinity feasibility before calling metal_speciation(). "
                f"PHREEQC error: {error_msg[:200]}"
            ) from e
        else:
            # Other error - re-raise
            raise

    # Allow precipitation of metal hydroxides and phosphates
    # These are the key minerals for coagulation (verified in phreeqc.dat)
    minerals_to_check = []
    if dose_fe_mg_l > 0:
        minerals_to_check.extend(["Fe(OH)3(a)", "Strengite"])  # Fe(OH)3(a), FePO4:2H2O
    if dose_al_mg_l > 0:
        minerals_to_check.extend(["Gibbsite", "Berlinite"])  # Al(OH)3, AlPO4

    minerals_formed = []
    for mineral in minerals_to_check:
        try:
            si = sol.si(mineral)
            if si > 0:  # Oversaturated
                sol.desaturate(mineral, to_si=0)  # Precipitate to equilibrium
                minerals_formed.append(mineral)
        except Exception as e:
            logger.warning(f"Could not check mineral {mineral}: {e}")

    # Extract results using correct phreeqpython syntax
    ph_out = sol.pH

    # Alkalinity: calculate from carbonate species (mol/kgw)
    # Alk (meq/L) ≈ [HCO3-] + 2[CO3-2] + [OH-] - [H+]
    hco3_mmol = sol.species.get('HCO3-', 0) * 1000  # mol/kgw -> mmol/L
    co3_mmol = sol.species.get('CO3-2', 0) * 1000
    oh_mmol = sol.species.get('OH-', 0) * 1000
    h_mmol = sol.species.get('H+', 0) * 1000
    alkalinity_out_meq = hco3_mmol + 2*co3_mmol + oh_mmol - h_mmol
    alkalinity_out = alkalinity_out_meq * 50.04  # mg/L as CaCO3
    alkalinity_in_meq = alkalinity_mg_l_caco3 / 50.04
    alkalinity_consumed_meq = alkalinity_in_meq - alkalinity_out_meq

    # Ionic strength
    ionic_strength = sol.I

    # Dissolved metals (in mg/L)
    fe_dissolved = sol.total("Fe", units='mg') if dose_fe_mg_l > 0 else 0.0
    al_dissolved = sol.total("Al", units='mg') if dose_al_mg_l > 0 else 0.0

    # Precipitated metals (input - dissolved)
    # Use max(0.0, ...) to avoid negative values from numerical precision issues
    fe_precipitated = max(0.0, dose_fe_mg_l - fe_dissolved) if dose_fe_mg_l > 0 else 0.0
    al_precipitated = max(0.0, dose_al_mg_l - al_dissolved) if dose_al_mg_l > 0 else 0.0

    # Convert to hydroxide mass
    # Fe(OH)3: MW = 106.87 g/mol, Fe: MW = 55.845 g/mol → ratio = 1.914
    # Al(OH)3: MW = 78.00 g/mol, Al: MW = 26.98 g/mol → ratio = 2.889
    fe_hydroxide_mg_l = fe_precipitated * 1.914
    al_hydroxide_mg_l = al_precipitated * 2.889

    # Phosphorus (in mg/L)
    # Clamp to avoid negative removal from numerical precision
    p_effluent = sol.total("P", units='mg')
    p_precipitated = max(0.0, influent_tp_mg_l - p_effluent)

    return {
        "ph_out": ph_out,
        "alkalinity_out_mg_l_caco3": max(0.0, alkalinity_out),
        "alkalinity_consumed_meq_l": alkalinity_consumed_meq,
        "fe_precipitated_mg_l": fe_hydroxide_mg_l,
        "al_precipitated_mg_l": al_hydroxide_mg_l,
        "total_hydroxide_mg_l": fe_hydroxide_mg_l + al_hydroxide_mg_l,
        "p_precipitated_mg_l": p_precipitated,
        "p_effluent_mg_l": p_effluent,
        # Ionic strengths (both pre-precipitation and equilibrium)
        "ionic_strength_mol_l": ionic_strength_dose,  # Pre-precipitation (for dose-response)
        "ionic_strength_equilibrium_mol_l": ionic_strength,  # Equilibrium (from PHREEQC)
        "fe_dissolved_mg_l": fe_dissolved,
        "al_dissolved_mg_l": al_dissolved,
        "minerals_formed": minerals_formed,
        "dose_fe_mg_l": dose_fe_mg_l,
        "dose_al_mg_l": dose_al_mg_l
    }


def check_alkalinity_feasibility(
    dose_fe_mg_l: float,
    dose_al_mg_l: float,
    alkalinity_mg_l_caco3: float,
    min_ph: float = 6.0
) -> Dict[str, Any]:
    """
    Check if alkalinity is sufficient for the proposed metal dose.

    Metal hydrolysis consumes alkalinity:
    - Fe³⁺: ~0.5 meq/L per 10 mg/L Fe
    - Al³⁺: ~0.6 meq/L per 10 mg/L Al

    Args:
        dose_fe_mg_l: Ferric iron dose (mg/L as Fe).
        dose_al_mg_l: Aluminum dose (mg/L as Al).
        alkalinity_mg_l_caco3: Available alkalinity (mg/L as CaCO3).
        min_ph: Minimum acceptable pH (default 6.0).

    Returns:
        Dictionary with:
        - feasible: Boolean, True if alkalinity sufficient
        - alkalinity_required_mg_l: Estimated alkalinity needed
        - alkalinity_margin_mg_l: Surplus (+) or deficit (-)
        - warning: Warning message if not feasible

    Example:
        >>> check = check_alkalinity_feasibility(
        ...     dose_fe_mg_l=30.0,
        ...     alkalinity_mg_l_caco3=80.0
        ... )
        >>> if not check['feasible']:
        ...     print(check['warning'])
    """
    # Empirical alkalinity consumption (meq/L per 10 mg/L metal)
    # Fe: ~0.5 meq/L per 10 mg/L Fe
    # Al: ~0.6 meq/L per 10 mg/L Al
    alk_consumed_fe_meq = (dose_fe_mg_l / 10.0) * 0.5
    alk_consumed_al_meq = (dose_al_mg_l / 10.0) * 0.6
    alk_consumed_total_meq = alk_consumed_fe_meq + alk_consumed_al_meq

    # Convert to mg/L as CaCO3
    alk_required_mg_l = alk_consumed_total_meq * 50.04

    # Margin
    alk_margin = alkalinity_mg_l_caco3 - alk_required_mg_l

    # Check feasibility (leave 20 mg/L CaCO3 buffer)
    feasible = alk_margin > 20.0

    warning = None
    if not feasible:
        warning = (
            f"Insufficient alkalinity: {alkalinity_mg_l_caco3:.0f} mg/L CaCO3 available, "
            f"but {alk_required_mg_l:.0f} mg/L required for dose. "
            f"pH will drop below {min_ph:.1f}. Add alkalinity or reduce dose."
        )

    return {
        "feasible": feasible,
        "alkalinity_required_mg_l": alk_required_mg_l,
        "alkalinity_margin_mg_l": alk_margin,
        "alkalinity_consumed_meq_l": alk_consumed_total_meq,
        "warning": warning
    }


def stoichiometric_p_removal_floor(
    influent_tp_mg_l: float,
    metal_type: str = "fe"
) -> float:
    """
    Calculate minimum metal dose for stoichiometric P removal.

    Stoichiometric ratios (by mass):
    - Fe:P ≈ 1.8:1 (as Fe:P, typical 1.5-2.0)
    - Al:P ≈ 0.87:1 (as Al:P, typical 0.8-1.0)

    Args:
        influent_tp_mg_l: Influent total phosphorus (mg/L as P).
        metal_type: "fe" or "al".

    Returns:
        Minimum metal dose (mg/L) for stoichiometric precipitation.

    Example:
        >>> # 5 mg/L P needs at least:
        >>> fe_min = stoichiometric_p_removal_floor(5.0, "fe")
        >>> print(f"Minimum Fe dose: {fe_min:.1f} mg/L")
        Minimum Fe dose: 9.0 mg/L
    """
    if metal_type.lower() == "fe":
        # Fe:P ≈ 1.8:1
        return influent_tp_mg_l * 1.8
    elif metal_type.lower() == "al":
        # Al:P ≈ 0.87:1
        return influent_tp_mg_l * 0.87
    else:
        raise ValueError(f"Unknown metal_type: {metal_type}. Use 'fe' or 'al'.")
