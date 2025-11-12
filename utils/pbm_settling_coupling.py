"""
PBM-Settling Coupling Utility

Connects Population Balance Model size distributions with fractal settling
velocities and hindered settling corrections.

This module provides the integration layer between:
- Module 3 (PBM): Provides particle number concentrations per size bin
- Module 4 (Fractal Settling): Computes free-settling velocities
- Hindered Settling: Applies Takács concentration-dependent corrections

Key Functions:
- compute_bin_settling_velocities(): Main coupling function
- compute_bin_mass_concentrations(): Convert N(d) to C(d) using fractal density
- compute_total_tss(): Integrate bin masses to get bulk TSS

References:
    Integration pattern from Codex findings:
    "Production clarifier models recalculate a single hindered velocity per
    vertical layer each timestep based on bulk TSS"

Attribution:
    Hybrid approach (free-settling × hindered factor) follows QSDsan/BSM2 pattern
    while adding size resolution from PBM framework.
"""

import numpy as np
from typing import Union, Optional, Dict, Any
from fractal_settling import FractalFlocProperties, FractalSettlingVelocity
from hindered_settling import (
    apply_hindered_correction_to_bins,
    PRIMARY_PARAMS,
    BSM2_PARAMS
)


def compute_bin_mass_concentrations(
    diameter_bins: np.ndarray,
    number_concentrations: np.ndarray,
    floc_properties: FractalFlocProperties
) -> np.ndarray:
    """
    Convert number concentrations to mass concentrations using fractal density.

    For each size bin i:
        C_i [kg/m³] = N_i [#/m³] × ρ_eff(d_i) [kg/m³] × V_sphere(d_i) [m³]

    where V_sphere = (π/6) × d³

    Args:
        diameter_bins: Bin center diameters [m], shape (N_bins,)
        number_concentrations: Number concentrations [#/m³], shape (N_bins,)
        floc_properties: FractalFlocProperties instance for density calculation

    Returns:
        mass_concentrations: Mass concentration per bin [kg/m³], shape (N_bins,)

    Notes:
        Uses fractal-corrected density ρ_eff(d) for each bin.
        For fractal aggregates with Df < 3, larger particles have lower density.
    """
    # Particle volumes (spherical envelope)
    volumes = (np.pi / 6.0) * diameter_bins**3

    # Effective densities (fractal-corrected)
    rho_eff = floc_properties.effective_density(diameter_bins)

    # Mass concentrations per bin
    mass_concentrations = number_concentrations * rho_eff * volumes

    return mass_concentrations


def compute_total_tss(
    diameter_bins: np.ndarray,
    number_concentrations: np.ndarray,
    floc_properties: FractalFlocProperties
) -> float:
    """
    Calculate total TSS by integrating bin mass concentrations.

    TSS [kg/m³] = Σ C_i = Σ [N_i × ρ_eff(d_i) × V(d_i)]

    Args:
        diameter_bins: Bin diameters [m]
        number_concentrations: Number concentrations [#/m³]
        floc_properties: FractalFlocProperties instance

    Returns:
        TSS: Total suspended solids [kg/m³]

    Notes:
        This is the "bulk TSS" used for hindered settling correction.
        Takács hindered factor is computed from this total concentration.
    """
    mass_concentrations = compute_bin_mass_concentrations(
        diameter_bins, number_concentrations, floc_properties
    )

    TSS = np.sum(mass_concentrations)

    return TSS


def compute_bin_settling_velocities(
    diameter_bins: np.ndarray,
    number_concentrations: np.ndarray,
    floc_properties: FractalFlocProperties,
    settling_calculator: FractalSettlingVelocity,
    X_influent: float,
    use_hindered_correction: bool = True,
    takacs_params: Optional[Dict[str, Any]] = None,
    return_intermediate: bool = False
) -> Union[np.ndarray, Dict[str, np.ndarray]]:
    """
    Compute hindered settling velocities for size-resolved distribution.

    This is the main coupling function that implements the hybrid approach:

    1. Compute free-settling velocities per bin using fractal settling (Module 4)
    2. Calculate total TSS from size distribution (fractal density)
    3. Apply Takács hindered correction based on bulk TSS

    vs_hindered(i) = vs_free(i) × f_hinder(TSS_total)

    Args:
        diameter_bins: Particle diameters [m], shape (N_bins,)
        number_concentrations: Number concentrations [#/m³], shape (N_bins,)
        floc_properties: FractalFlocProperties instance
        settling_calculator: FractalSettlingVelocity instance
        X_influent: Influent TSS concentration [kg/m³] for Takács X_min
        use_hindered_correction: If False, returns only free-settling velocities
        takacs_params: Takács parameters (v0_max, rh, rp, fns), uses PRIMARY_PARAMS if None
        return_intermediate: If True, returns dict with intermediate results

    Returns:
        If return_intermediate=False:
            vs_hindered: Hindered settling velocities [m/day], shape (N_bins,)

        If return_intermediate=True:
            Dictionary with keys:
                'vs_hindered': Hindered velocities [m/day]
                'vs_free': Free-settling velocities [m/day]
                'mass_concentrations': Mass per bin [kg/m³]
                'TSS_total': Total TSS [kg/m³]
                'hindrance_factor': Dimensionless factor [-]

    Notes:
        Velocities returned in m/day (not m/s) for QSDsan consistency.
        From Codex: "Hindered settling is parameterized on total TSS because
        that's the measurable control variable"

    Examples:
        >>> # Basic usage with default primary clarifier parameters
        >>> vs_hindered = compute_bin_settling_velocities(
        ...     diameter_bins, number_conc, floc_props, settling_calc,
        ...     X_influent=0.2  # 200 mg/L
        ... )

        >>> # Get diagnostic information
        >>> results = compute_bin_settling_velocities(
        ...     diameter_bins, number_conc, floc_props, settling_calc,
        ...     X_influent=0.2, return_intermediate=True
        ... )
        >>> print(f"Total TSS: {results['TSS_total']*1000:.1f} mg/L")
        >>> print(f"Hindrance factor: {results['hindrance_factor']:.3f}")
    """
    # Default to primary clarifier parameters
    if takacs_params is None:
        takacs_params = PRIMARY_PARAMS.copy()

    # Step 1: Compute free-settling velocities using fractal settling
    # Returns velocities in m/s
    vs_free_m_s = settling_calculator.settling_velocity(diameter_bins)

    # Convert to m/day for QSDsan consistency
    vs_free = vs_free_m_s * 86400.0  # s/day

    # Step 2: Calculate total TSS from size distribution
    mass_concentrations = compute_bin_mass_concentrations(
        diameter_bins, number_concentrations, floc_properties
    )
    TSS_total = np.sum(mass_concentrations)

    # Step 3: Apply hindered settling correction
    if use_hindered_correction:
        vs_hindered = apply_hindered_correction_to_bins(
            free_settling_velocities=vs_free,
            bin_concentrations=mass_concentrations,
            X_influent=X_influent,
            use_total_concentration=True,  # Standard approach from Codex
            **takacs_params
        )

        # Calculate hindrance factor for diagnostics
        from hindered_settling import hindrance_factor
        f_hinder = hindrance_factor(TSS_total, X_influent, **takacs_params)
    else:
        vs_hindered = vs_free
        f_hinder = 1.0

    # Return results
    if return_intermediate:
        return {
            'vs_hindered': vs_hindered,
            'vs_free': vs_free,
            'mass_concentrations': mass_concentrations,
            'TSS_total': TSS_total,
            'hindrance_factor': f_hinder
        }
    else:
        return vs_hindered


def compute_settling_fluxes(
    diameter_bins: np.ndarray,
    number_concentrations: np.ndarray,
    hindered_velocities: np.ndarray,
    floc_properties: FractalFlocProperties
) -> np.ndarray:
    """
    Calculate solids settling flux for each size bin.

    J(i) [kg/(m²·day)] = C(i) [kg/m³] × vs_hindered(i) [m/day]

    This is the flux used in the layer-to-layer settling transport in
    the _compile_ODE() implementation.

    Args:
        diameter_bins: Bin diameters [m]
        number_concentrations: Number concentrations [#/m³]
        hindered_velocities: Hindered settling velocities [m/day]
        floc_properties: FractalFlocProperties instance

    Returns:
        fluxes: Settling flux per bin [kg/(m²·day)], shape (N_bins,)

    Notes:
        Mass flux, not number flux. For ODE system, this will need to be
        converted back to number flux: J_N = J_mass / (ρ_eff × V_particle)
    """
    mass_concentrations = compute_bin_mass_concentrations(
        diameter_bins, number_concentrations, floc_properties
    )

    fluxes = mass_concentrations * hindered_velocities

    return fluxes


def settling_velocity_summary(
    diameter_bins: np.ndarray,
    number_concentrations: np.ndarray,
    floc_properties: FractalFlocProperties,
    settling_calculator: FractalSettlingVelocity,
    X_influent: float,
    takacs_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate comprehensive summary of settling velocities across size distribution.

    Useful for debugging and validation of physics integration.

    Args:
        diameter_bins: Bin diameters [m]
        number_concentrations: Number concentrations [#/m³]
        floc_properties: FractalFlocProperties instance
        settling_calculator: FractalSettlingVelocity instance
        X_influent: Influent TSS [kg/m³]
        takacs_params: Takács parameters

    Returns:
        Dictionary with diagnostic information:
            - 'diameters_um': Bin diameters [μm]
            - 'vs_free_m_day': Free-settling velocities [m/day]
            - 'vs_hindered_m_day': Hindered velocities [m/day]
            - 'mass_concentrations_mg_L': Mass per bin [mg/L]
            - 'TSS_total_mg_L': Total TSS [mg/L]
            - 'hindrance_factor': Dimensionless factor [-]
            - 'effective_densities': ρ_eff per bin [kg/m³]
            - 'reynolds_numbers': Re per bin [-]

    Examples:
        >>> summary = settling_velocity_summary(
        ...     diameter_bins, number_conc, floc_props, settling_calc,
        ...     X_influent=0.2
        ... )
        >>> print(f"TSS: {summary['TSS_total_mg_L']:.1f} mg/L")
        >>> print(f"Hindrance factor: {summary['hindrance_factor']:.3f}")
        >>> print(f"Fastest settling bin: {np.argmax(summary['vs_hindered_m_day'])}")
    """
    results = compute_bin_settling_velocities(
        diameter_bins, number_concentrations,
        floc_properties, settling_calculator, X_influent,
        use_hindered_correction=True,
        takacs_params=takacs_params,
        return_intermediate=True
    )

    # Additional diagnostics
    rho_eff = floc_properties.effective_density(diameter_bins)

    # Reynolds numbers (using hindered velocities)
    vs_hindered_m_s = results['vs_hindered'] / 86400.0
    Re = settling_calculator.reynolds_number(diameter_bins, vs_hindered_m_s)

    return {
        'diameters_um': diameter_bins * 1e6,
        'vs_free_m_day': results['vs_free'],
        'vs_hindered_m_day': results['vs_hindered'],
        'mass_concentrations_mg_L': results['mass_concentrations'] * 1000.0,
        'TSS_total_mg_L': results['TSS_total'] * 1000.0,
        'hindrance_factor': results['hindrance_factor'],
        'effective_densities': rho_eff,
        'reynolds_numbers': Re
    }
