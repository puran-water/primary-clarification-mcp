"""
DLVO Theory for Particle-Particle Collision Efficiency in Primary Clarifiers

This module implements the Derjaguin-Landau-Verwey-Overbeek (DLVO) theory
for calculating collision efficiency between floc particles in primary clarifiers.

Adapted from DAF-Sim (neuron-box/DAF-Sim) with modifications for:
- Particle-particle interactions (not bubble-particle)
- Log-sum-exp numerical stability (Codex requirement)
- Hamaker constant matrix for different particle types
- Capped α formulation for attachment efficiency
- Temperature propagation throughout calculations

Original DAF-Sim References:
    - Han et al. (2001). Water Science and Technology, 43(8), 139-144.
    - Israelachvili, J. N. (2011). Intermolecular and Surface Forces (3rd ed.).

Additional References:
    - Edzwald, J. K. (2010). Water Research, 44, 2077-2106.
    - Codex peer review (conversation 019a70e1-b0cf-7b92-b8eb-14a317fa94a0)

Attribution:
    Core DLVO formulations adapted from neuron-box/DAF-Sim
    (https://github.com/neuron-box/DAF-Sim)
    Assuming permission granted; will remove if denied.

License: To be determined upon DAF-Sim license clarification
"""

import math
import numpy as np
from typing import Dict, Tuple, Optional


# Physical constants
VACUUM_PERMITTIVITY = 8.854187817e-12  # ε₀ [F/m or C²/(N·m²)]
ELEMENTARY_CHARGE = 1.602176634e-19    # e [C]
BOLTZMANN_CONSTANT = 1.380649e-23      # k_B [J/K]
AVOGADRO_NUMBER = 6.02214076e23        # N_A [1/mol]


# Hamaker constant matrix [J]
# Literature-validated values (Edzwald 2010, Han 2002, Okada et al. 1990)
HAMAKER_CONSTANTS = {
    "solid_solid": 5.0e-20,      # Typical for mineral particles in water
    "oily_solid": 3.5e-20,       # Oil-contaminated particles (lower end)
    "organic_solid": 4.0e-20,    # Organic flocs with mineral particles
    "default": 4.5e-20,          # Conservative mid-range value
}


def safe_exp(x: float) -> float:
    """
    Numerically stable exponential using log-sum-exp trick.

    Clips exponent to prevent overflow/underflow.
    Codex requirement for numerical stability.

    Args:
        x: Exponent value

    Returns:
        exp(x) with safe clipping
    """
    # Clip to prevent overflow (exp(700) ≈ 1e304, near float64 max)
    # and underflow (exp(-700) ≈ 1e-304, near float64 min)
    x_safe = np.clip(x, -700.0, 700.0)
    return math.exp(x_safe)


def calculate_water_dielectric_constant(temperature_c: float) -> float:
    """
    Calculate temperature-dependent relative permittivity of water.

    Uses simplified Fernández et al. (1997) correlation for liquid water
    at 1 atm, valid for 0-100°C.

    ε_r(T) ≈ 87.74 - 0.40008·T + 9.398×10⁻⁴·T² - 1.410×10⁻⁶·T³

    Args:
        temperature_c: Temperature [°C]

    Returns:
        Relative permittivity ε_r [-]

    References:
        Fernández et al. (1997). J. Phys. Chem. Ref. Data, 26(4), 1125-1166.
    """
    T = temperature_c
    # Simplified polynomial fit (accurate to ~0.5% for 0-50°C)
    epsilon_r = 87.74 - 0.40008*T + 9.398e-4*T**2 - 1.410e-6*T**3

    # Clamp to reasonable range
    return np.clip(epsilon_r, 70.0, 90.0)


def calculate_debye_length(
    ionic_strength_M: float,
    temperature_c: float = 20.0,
    dielectric_constant: Optional[float] = None
) -> float:
    """
    Calculate Debye screening length (λ_D = κ⁻¹).

    λ_D = √(ε₀ε_r k_B T / (2 N_A e² I))

    Simplified form at 25°C: λ_D ≈ 0.304/√I [nm]

    Args:
        ionic_strength_M: Ionic strength [mol/L = M]
        temperature_c: Temperature [°C]
        dielectric_constant: Relative dielectric constant (optional, auto-computed if None)

    Returns:
        Debye length [m]

    Raises:
        ValueError: If ionic strength is non-positive
    """
    # Validate ionic strength (Codex requirement)
    if ionic_strength_M <= 0:
        raise ValueError(
            f"Ionic strength must be positive, got {ionic_strength_M} M. "
            "For distilled water, use a small value like 1e-6 M."
        )

    temperature_K = temperature_c + 273.15

    # Use temperature-dependent dielectric constant if not provided (Codex requirement)
    if dielectric_constant is None:
        dielectric_constant = calculate_water_dielectric_constant(temperature_c)

    # Convert ionic strength from M to mol/m³
    I_mol_per_m3 = ionic_strength_M * 1000.0

    # Debye length calculation
    numerator = (VACUUM_PERMITTIVITY * dielectric_constant *
                 BOLTZMANN_CONSTANT * temperature_K)
    denominator = (2.0 * AVOGADRO_NUMBER * ELEMENTARY_CHARGE**2 * I_mol_per_m3)

    lambda_D = math.sqrt(numerator / denominator)

    return lambda_D  # [m]


def calculate_interaction_energy(
    h: float,
    d1: float,
    d2: float,
    zeta1_mV: float,
    zeta2_mV: float,
    ionic_strength_M: float,
    temperature_c: float = 20.0,
    hamaker_constant: Optional[float] = None,
    particle_type: str = "default"
) -> Tuple[float, float, float]:
    """
    Calculate DLVO interaction energy between two spherical particles.

    Based on Derjaguin approximation (valid for h << R₁, R₂).

    Energy Components:
    ------------------
    1. Van der Waals (attractive):
       V_vdW = -A * R₁ * R₂ / (6 * h * (R₁ + R₂))

    2. Electrostatic double layer (Hogg-Healy-Fuerstenau constant potential):
       V_EDL = 2π * ε₀ * εᵣ * R_eff *
               [(ψ₁² + ψ₂²) * ln[1 - exp(-2κh)] + 2ψ₁ψ₂ * ln[1 + exp(-κh)]]

       where R_eff = R₁*R₂/(R₁+R₂)

       For like charges: repulsive (positive)
       For opposite charges: attractive (negative)

    Args:
        h: Surface-to-surface separation [m]
        d1: Diameter of particle 1 [m]
        d2: Diameter of particle 2 [m]
        zeta1_mV: Zeta potential of particle 1 [mV]
        zeta2_mV: Zeta potential of particle 2 [mV]
        ionic_strength_M: Ionic strength [M]
        temperature_c: Temperature [°C]
        hamaker_constant: Hamaker constant [J] (optional, uses matrix if None)
        particle_type: Type for Hamaker lookup ("solid_solid", "oily_solid", etc.)

    Returns:
        Tuple of (V_vdW, V_EDL, V_total) [J]
    """
    # Handle contact case
    if h <= 0:
        h = 1e-10  # 0.1 nm minimum separation

    # Particle radii
    R1 = d1 / 2.0
    R2 = d2 / 2.0

    # Temperature in Kelvin
    T = temperature_c + 273.15
    kT = BOLTZMANN_CONSTANT * T

    # Hamaker constant
    if hamaker_constant is None:
        A = HAMAKER_CONSTANTS.get(particle_type, HAMAKER_CONSTANTS["default"])
    else:
        A = hamaker_constant

    # Van der Waals energy (attractive, negative)
    V_vdW = -A * R1 * R2 / (6.0 * h * (R1 + R2))

    # Electrostatic energy - Hogg-Healy-Fuerstenau (HHF) constant potential form
    # Convert zeta potentials from mV to V
    zeta1_V = zeta1_mV / 1000.0
    zeta2_V = zeta2_mV / 1000.0

    # Calculate Debye length and κ with temperature-dependent dielectric constant
    epsilon_r = calculate_water_dielectric_constant(temperature_c)
    lambda_D = calculate_debye_length(ionic_strength_M, temperature_c, epsilon_r)
    kappa = 1.0 / lambda_D

    # Derjaguin approximation for EDL energy
    R_eff = R1 * R2 / (R1 + R2)  # Effective radius

    # HHF constant potential formula (complete form - Codex requirement):
    # V_EDL = 2π·ε₀·ε_r·R_eff·[(ψ₁²+ψ₂²)·ln[1-exp(-2κh)] + 2ψ₁ψ₂·ln[1+exp(-κh)]]
    #
    # Valid for κR >> 1 (true for I ≥ 10⁻⁴ M and R ≥ 0.1 μm)
    #
    # References:
    #   - Hogg, Healy, Fuerstenau (1966). Trans. Faraday Soc., 62, 1638-1651.
    #   - Codex review (2025-11-11)

    geom_factor = 2.0 * math.pi * VACUUM_PERMITTIVITY * epsilon_r * R_eff

    # Use log1p for numerical precision (Codex requirement)
    kappa_h = kappa * h

    if kappa_h < 15:
        # Full HHF formula with numerically stable logarithms
        # ln[1 - exp(-2κh)] for like charges (repulsive term)
        term1 = (zeta1_V**2 + zeta2_V**2) * math.log1p(-safe_exp(-2.0 * kappa_h))

        # ln[1 + exp(-κh)] for cross term
        term2 = 2.0 * zeta1_V * zeta2_V * math.log1p(safe_exp(-kappa_h))

        V_EDL = geom_factor * (term1 + term2)
    else:
        # Far separation (κh > 15): exponentials underflow, use limiting forms
        # ln[1-exp(-2κh)] ≈ ln[1] = 0 (negligible)
        # ln[1+exp(-κh)] ≈ exp(-κh)
        V_EDL = geom_factor * 2.0 * zeta1_V * zeta2_V * safe_exp(-kappa_h)

    # Total interaction energy
    V_total = V_vdW + V_EDL

    return V_vdW, V_EDL, V_total


def calculate_energy_barrier(
    d1: float,
    d2: float,
    zeta1_mV: float,
    zeta2_mV: float,
    ionic_strength_M: float,
    temperature_c: float = 20.0,
    hamaker_constant: Optional[float] = None,
    particle_type: str = "default",
    h_min: float = 1e-9,
    h_max: float = 100e-9,
    n_points: int = 100
) -> Dict[str, float]:
    """
    Calculate maximum energy barrier in DLVO profile.

    Scans from h_min to h_max to find peak energy.

    Args:
        d1: Diameter of particle 1 [m]
        d2: Diameter of particle 2 [m]
        zeta1_mV: Zeta potential of particle 1 [mV]
        zeta2_mV: Zeta potential of particle 2 [mV]
        ionic_strength_M: Ionic strength [M]
        temperature_c: Temperature [°C]
        hamaker_constant: Hamaker constant [J]
        particle_type: Type for Hamaker lookup
        h_min: Minimum separation to scan [m] (default 1 nm)
        h_max: Maximum separation to scan [m] (default 100 nm)
        n_points: Number of points to sample

    Returns:
        Dictionary with:
        - "barrier_J": Maximum energy barrier [J]
        - "barrier_kT": Energy barrier in kT units [-]
        - "barrier_height_m": Separation at barrier maximum [m]
        - "is_favorable": True if barrier < 10 kT
    """
    T = temperature_c + 273.15
    kT = BOLTZMANN_CONSTANT * T

    # Sample energy profile
    h_values = np.linspace(h_min, h_max, n_points)
    energies = [
        calculate_interaction_energy(
            h, d1, d2, zeta1_mV, zeta2_mV, ionic_strength_M,
            temperature_c, hamaker_constant, particle_type
        )[2]  # V_total
        for h in h_values
    ]

    # Find maximum energy
    max_idx = np.argmax(energies)
    max_energy = energies[max_idx]
    barrier_height = h_values[max_idx]

    # If maximum energy is negative, there's no repulsive barrier
    # (van der Waals attraction dominates everywhere)
    if max_energy < 0:
        max_energy = 0.0
        barrier_kT = 0.0
        is_favorable = True
    else:
        # Convert to kT units
        barrier_kT = max_energy / kT
        # Favorable if barrier < 10 kT (Han et al. 2001, Edzwald 2010)
        is_favorable = barrier_kT < 10.0

    return {
        "barrier_J": max_energy,
        "barrier_kT": barrier_kT,
        "barrier_height_m": barrier_height,
        "is_favorable": is_favorable,
    }


def calculate_attachment_efficiency_capped(
    barrier_kT: float,
    n_factor: float = 3.0
) -> float:
    """
    Calculate attachment efficiency using capped formulation.

    Codex-validated capped α formulation:
        α = 1 / (1 + ΔΦ/(n·kT))

    Where:
    - ΔΦ = energy barrier [J]
    - n = empirical factor (typically 3.0)
    - kT = thermal energy [J]

    This formulation ensures α ∈ [0, 1] and provides gradual decay
    with increasing barrier height.

    Args:
        barrier_kT: Energy barrier in kT units [-]
        n_factor: Empirical factor (default 3.0)

    Returns:
        Attachment efficiency α ∈ [0, 1]
    """
    if barrier_kT <= 0:
        # Favorable (attractive) - perfect attachment
        return 1.0

    # Capped formulation
    alpha = 1.0 / (1.0 + barrier_kT / n_factor)

    # Enforce bounds [10⁻⁴, 1] (Codex requirement)
    alpha = np.clip(alpha, 1e-4, 1.0)

    return alpha


def calculate_attachment_efficiency_arrhenius(
    barrier_kT: float
) -> float:
    """
    Calculate attachment efficiency using Arrhenius formulation.

    Alternative formulation from DAF-Sim collision_efficiency.py:
        - If ΔΦ ≤ 0: α = 1.0 (favorable)
        - If 0 < ΔΦ < 10 kT: α = 1 - exp(-10/ΔΦ_kT)
        - If ΔΦ ≥ 10 kT: α = exp(-ΔΦ_kT/2)

    Args:
        barrier_kT: Energy barrier in kT units [-]

    Returns:
        Attachment efficiency α ∈ [0, 1]
    """
    if barrier_kT <= 0:
        # Favorable (attractive or no barrier)
        return 1.0
    elif barrier_kT < 10.0:
        # Low barrier - high attachment probability
        # Handle near-zero barriers to avoid division issues
        if barrier_kT < 0.01:
            return 1.0
        alpha = 1.0 - safe_exp(-10.0 / barrier_kT)
    else:
        # High barrier - low attachment probability
        alpha = safe_exp(-barrier_kT / 2.0)

    # Enforce bounds
    alpha = np.clip(alpha, 1e-4, 1.0)

    return alpha


def calculate_collision_efficiency(
    d1: float,
    d2: float,
    zeta1_mV: float,
    zeta2_mV: float,
    ionic_strength_M: float,
    temperature_c: float = 20.0,
    hamaker_constant: Optional[float] = None,
    particle_type: str = "default",
    alpha_method: str = "capped",
    n_factor: float = 3.0
) -> Dict[str, float]:
    """
    Calculate particle-particle collision efficiency α using DLVO theory.

    Main API for collision efficiency calculations in primary clarifiers.

    Workflow:
    ---------
    1. Calculate DLVO energy barrier
    2. Determine attachment efficiency (α) using specified method
    3. Return comprehensive diagnostics

    Args:
        d1: Diameter of particle 1 [m]
        d2: Diameter of particle 2 [m]
        zeta1_mV: Zeta potential of particle 1 [mV]
        zeta2_mV: Zeta potential of particle 2 [mV]
        ionic_strength_M: Ionic strength [M]
        temperature_c: Temperature [°C]
        hamaker_constant: Hamaker constant [J] (uses matrix if None)
        particle_type: Type for Hamaker lookup
        alpha_method: "capped" (default) or "arrhenius"
        n_factor: Empirical factor for capped method (default 3.0)

    Returns:
        Dictionary with:
        - "alpha": Collision efficiency α ∈ [0, 1]
        - "barrier_J": Energy barrier [J]
        - "barrier_kT": Energy barrier in kT units
        - "barrier_height_m": Separation at barrier [m]
        - "is_favorable": Boolean (barrier < 10 kT)
        - "V_vdW_at_contact": Van der Waals energy at contact [J]
        - "V_EDL_at_contact": Electrostatic energy at contact [J]
        - "debye_length_m": Debye screening length [m]
        - "method_used": "capped" or "arrhenius"

    Example:
        >>> result = calculate_collision_efficiency(
        ...     d1=30e-6, d2=40e-6,           # 30 and 40 μm flocs
        ...     zeta1_mV=-5.0, zeta2_mV=-5.0, # Near-neutral (coagulated)
        ...     ionic_strength_M=0.01,        # 10 mM
        ...     temperature_c=20.0
        ... )
        >>> print(f"α = {result['alpha']:.3f}")
        >>> print(f"Barrier = {result['barrier_kT']:.1f} kT")
    """
    # Calculate energy barrier
    barrier_info = calculate_energy_barrier(
        d1, d2, zeta1_mV, zeta2_mV, ionic_strength_M,
        temperature_c, hamaker_constant, particle_type
    )

    # Calculate attachment efficiency
    if alpha_method == "capped":
        alpha = calculate_attachment_efficiency_capped(
            barrier_info["barrier_kT"], n_factor
        )
    elif alpha_method == "arrhenius":
        alpha = calculate_attachment_efficiency_arrhenius(
            barrier_info["barrier_kT"]
        )
    else:
        raise ValueError(f"Unknown alpha_method: {alpha_method}. Use 'capped' or 'arrhenius'.")

    # Calculate energies at contact (h = 0.1 nm)
    V_vdW_contact, V_EDL_contact, _ = calculate_interaction_energy(
        h=1e-10, d1=d1, d2=d2, zeta1_mV=zeta1_mV, zeta2_mV=zeta2_mV,
        ionic_strength_M=ionic_strength_M, temperature_c=temperature_c,
        hamaker_constant=hamaker_constant, particle_type=particle_type
    )

    # Calculate Debye length
    debye_length = calculate_debye_length(ionic_strength_M, temperature_c)

    return {
        "alpha": alpha,
        "barrier_J": barrier_info["barrier_J"],
        "barrier_kT": barrier_info["barrier_kT"],
        "barrier_height_m": barrier_info["barrier_height_m"],
        "is_favorable": barrier_info["is_favorable"],
        "V_vdW_at_contact": V_vdW_contact,
        "V_EDL_at_contact": V_EDL_contact,
        "debye_length_m": debye_length,
        "method_used": alpha_method,
    }


# Convenience function for batch calculations
def calculate_alpha_matrix(
    diameters: list,
    zeta_potentials_mV: list,
    ionic_strength_M: float,
    temperature_c: float = 20.0,
    **kwargs
) -> np.ndarray:
    """
    Calculate collision efficiency matrix for a set of particle sizes.

    Useful for population balance model (PBM) integration where we need
    α(i,j) for all size bin combinations.

    Args:
        diameters: List/array of particle diameters [m]
        zeta_potentials_mV: List/array of zeta potentials [mV] (one per size bin)
        ionic_strength_M: Ionic strength [M]
        temperature_c: Temperature [°C]
        **kwargs: Additional arguments for calculate_collision_efficiency

    Returns:
        n×n matrix of collision efficiencies α[i,j]
    """
    n = len(diameters)
    alpha_matrix = np.zeros((n, n))

    for i in range(n):
        for j in range(n):
            result = calculate_collision_efficiency(
                d1=diameters[i],
                d2=diameters[j],
                zeta1_mV=zeta_potentials_mV[i],
                zeta2_mV=zeta_potentials_mV[j],
                ionic_strength_M=ionic_strength_M,
                temperature_c=temperature_c,
                **kwargs
            )
            alpha_matrix[i, j] = result["alpha"]

    return alpha_matrix
