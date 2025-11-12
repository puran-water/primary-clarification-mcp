"""
Hindered Settling Velocity Calculations

Implements concentration-dependent settling velocity corrections using
Takács double-exponential and Vesilind models (from QSDsan/BSM2).

Key Features:
- Vesilind exponential: vs = v0·exp(-rh·X)
- Takács double-exponential with non-settleable fraction
- Hindrance factor for coupling with fractal settling

References:
    - Vesilind (1968). J. Sanit. Eng. Div., 94(SA2), 229-237.
    - Takács et al. (1991). Water Research, 25(10), 1263-1271.
    - QSD-Group/QSDsan (qsdsan/sanunits/_clarifier.py)
    - fau-evt/bsm2-python (settler1d_bsm2.py)
"""

import numpy as np
from typing import Union, Optional


# BSM2 parameter set (secondary clarifier, from Codex findings)
BSM2_PARAMS = {
    "v0_max": 474.0,  # m/day
    "rh": 0.000576,  # m³/kg
    "rp": 0.00286,  # m³/kg
    "fns": 0.00228,  # -
    "v_max_practical": 250.0  # m/day
}

# Primary clarifier parameters (typical values from literature)
PRIMARY_PARAMS = {
    "v0_max": 400.0,  # m/day (lower than secondary)
    "rh": 0.0003,  # m³/kg (less hindered than activated sludge)
    "rp": 0.002,  # m³/kg
    "fns": 0.005,  # - (higher non-settleable fraction)
    "v_max_practical": 300.0  # m/day
}


def takacs_velocity(
    X: Union[float, np.ndarray],
    X_influent: float,
    v0_max: float = 474.0,
    rh: float = 0.000576,
    rp: float = 0.00286,
    fns: float = 0.00228,
    v_max_practical: Optional[float] = None
) -> Union[float, np.ndarray]:
    """
    Calculate settling velocity using Takács double-exponential model.
    
    vs = max(0, v0·[exp(-rh·(X - X_min)) - exp(-rp·(X - X_min))])
    
    Capped at v_max_practical. This is the formulation used in QSDsan
    FlatBottomCircularClarifier and BSM2.
    
    Parameters
    ----------
    X : float or ndarray
        Solids concentration [kg/m³]
    X_influent : float
        Influent concentration for X_min calculation [kg/m³]
    v0_max : float
        Maximum theoretical settling velocity [m/day]
    rh : float
        Hindered zone parameter [m³/kg]
    rp : float
        Low concentration parameter [m³/kg]
    fns : float
        Non-settleable fraction [-]
    v_max_practical : float, optional
        Practical maximum velocity [m/day], defaults to v0_max
    
    Returns
    -------
    vs : float or ndarray
        Settling velocity [m/day], non-negative and capped
    
    Notes
    -----
    From Codex findings: "QSDsan/BSM2 use Takács double-exponential with
    Vesilind's v0 as theoretical limit and v0_max_practical as imposed cap"
    """
    if v_max_practical is None:
        v_max_practical = v0_max
    
    # Non-settleable threshold
    X_min = fns * X_influent
    
    # Effective concentration
    X_eff = np.maximum(X - X_min, 0.0)
    
    # Takács double-exponential
    vs = v0_max * (np.exp(-rh * X_eff) - np.exp(-rp * X_eff))
    
    # Ensure non-negative
    vs = np.maximum(vs, 0.0)
    
    # Cap at practical maximum
    vs = np.minimum(vs, v_max_practical)
    
    return vs


def hindrance_factor(
    X: Union[float, np.ndarray],
    X_influent: float,
    v0_max: float = 474.0,
    rh: float = 0.000576,
    rp: float = 0.00286,
    fns: float = 0.00228,
    v_max_practical: Optional[float] = None
) -> Union[float, np.ndarray]:
    """
    Calculate dimensionless hindrance factor from Takács model.
    
    f_hinder = vs(X) / v0_max
    
    This factor can be multiplied by free-settling velocities from
    fractal settling module to obtain hindered velocities.
    
    Parameters
    ----------
    X : float or ndarray
        Solids concentration [kg/m³]
    X_influent : float
        Influent concentration [kg/m³]
    v0_max : float
        Maximum theoretical velocity [m/day]
    rh, rp, fns : float
        Takács parameters
    v_max_practical : float, optional
        Practical maximum [m/day]
    
    Returns
    -------
    f : float or ndarray
        Hindrance factor [-] in range [0, 1]
    
    Notes
    -----
    From Codex: "Production clarifier models recalculate a single hindered
    velocity per vertical layer each timestep based on bulk TSS"
    """
    vs = takacs_velocity(X, X_influent, v0_max, rh, rp, fns, v_max_practical)
    factor = vs / v0_max
    
    # Ensure bounds [0, 1]
    factor = np.clip(factor, 0.0, 1.0)
    
    return factor


def apply_hindered_correction_to_bins(
    free_settling_velocities: np.ndarray,
    bin_concentrations: np.ndarray,
    X_influent: float,
    use_total_concentration: bool = True,
    **takacs_params
) -> np.ndarray:
    """
    Apply Takács hindered correction to size-resolved settling velocities.
    
    vs_hindered(i) = vs_free(i) · f_hinder(X_total)
    
    This implements the hybrid approach: fractal free-settling per bin
    multiplied by bulk hindered correction factor.
    
    Parameters
    ----------
    free_settling_velocities : ndarray
        Free settling velocities per bin [m/day], shape (N_bins,)
    bin_concentrations : ndarray
        Solids concentration per bin [kg/m³], shape (N_bins,)
    X_influent : float
        Influent total concentration [kg/m³]
    use_total_concentration : bool
        If True, use total TSS for hindrance (standard approach from Codex)
        If False, use bin-wise concentrations (experimental)
    **takacs_params : dict
        Takács parameters (v0_max, rh, rp, fns, v_max_practical)
    
    Returns
    -------
    vs_hindered : ndarray
        Hindered settling velocities [m/day], shape (N_bins,)
    
    Notes
    -----
    From Codex: "Hindered settling is parameterized on total TSS because
    that's the measurable control variable; if you have PBM detail, you
    can sum bin contributions and apply Vesilind/Takács per bin"
    """
    if use_total_concentration:
        # Standard approach: single hindrance factor from total TSS
        X_total = np.sum(bin_concentrations)
        f_hinder = hindrance_factor(X_total, X_influent, **takacs_params)
        vs_hindered = free_settling_velocities * f_hinder
    else:
        # Experimental: bin-wise hindrance factors
        vs_hindered = np.zeros_like(free_settling_velocities)
        for i in range(len(free_settling_velocities)):
            f_hinder_i = hindrance_factor(
                bin_concentrations[i], X_influent, **takacs_params
            )
            vs_hindered[i] = free_settling_velocities[i] * f_hinder_i
    
    return vs_hindered


def calculate_settling_flux_per_bin(
    hindered_velocities: np.ndarray,
    bin_concentrations: np.ndarray
) -> np.ndarray:
    """
    Calculate settling flux for each size bin.
    
    J(i) = X(i) · vs_hindered(i)
    
    Parameters
    ----------
    hindered_velocities : ndarray
        Hindered settling velocities [m/day], shape (N_bins,)
    bin_concentrations : ndarray
        Solids concentrations [kg/m³], shape (N_bins,)
    
    Returns
    -------
    fluxes : ndarray
        Settling fluxes [kg/(m²·day)], shape (N_bins,)
    """
    fluxes = bin_concentrations * hindered_velocities
    return fluxes
