"""
Fractal Aggregate Settling Velocity Calculations for Primary Clarifiers

Implements settling velocity models for fractal aggregates formed during
flocculation, accounting for size-dependent density and drag corrections.

Key Features:
- Fractal density scaling: ρ_eff(d) = ρ_w + (ρ_p - ρ_w)·(d/d₀)^(Df-3)
- Stokes settling with shape factor corrections
- Dietrich drag formulation for transitional/turbulent regimes
- Integration with Population Balance Model size distributions

References:
    - Logan & Wilkinson (1990). J. Hydraul. Eng., 116(9), 1121-1138.
    - Tambo & Watanabe (1979). Water Research, 13(5), 409-419.
    - Dietrich (1982). Water Resources Research, 18(6), 1615-1626.

Attribution:
    Fractal density and drag formulations adapted from:
    - neuron-box/DAF-Sim (floc_kinetics_pbm/src/properties.py)
    - AguaClara-Reach/aguaclara (research/floc_model.py)
"""

import numpy as np
from typing import Union, Dict
from scipy.constants import g as GRAVITY

# Physical constants
WATER_DENSITY = 998.0  # kg/m³ at 20°C
WATER_VISCOSITY = 1.002e-3  # Pa·s at 20°C


def calculate_water_density(temperature_c: float) -> float:
    """
    Calculate water density as function of temperature.

    Uses empirical correlation valid for 0-40°C.

    Args:
        temperature_c: Temperature [°C]

    Returns:
        Water density [kg/m³]

    References:
        Kell (1975). J. Chem. Eng. Data, 20(1), 97-105.
    """
    # Empirical fit for water density (accurate to ~0.01%)
    # ρ(T) = ρ_max · [1 - |T - T_max|^1.894 / C]
    # Simplified version for engineering applications
    T = temperature_c

    # Coefficients for 0-40°C range
    rho = 999.842594 + 0.06793952 * T - 0.009095290 * T**2 + \
          0.0001001685 * T**3 - 0.000001120083 * T**4 + \
          0.000000006536332 * T**5

    return rho


def calculate_water_viscosity(temperature_c: float) -> float:
    """
    Calculate dynamic viscosity of water as function of temperature.

    Uses Vogel-Fulcher-Tammann equation for liquid water.

    Args:
        temperature_c: Temperature [°C]

    Returns:
        Dynamic viscosity [Pa·s]
    """
    T = temperature_c + 273.15  # K

    # Vogel equation for water
    A = 2.414e-5  # Pa·s
    B = 247.8     # K
    C = 140.0     # K

    mu = A * 10**(B / (T - C))

    return mu


class FractalFlocProperties:
    """
    Calculate properties of fractal aggregates (flocs) for settling analysis.

    Implements fractal scaling laws for aggregate density and porosity
    as functions of size and fractal dimension.
    """

    def __init__(
        self,
        fractal_dimension: float = 2.3,
        primary_particle_diameter: float = 1e-6,  # 1 μm
        primary_particle_density: float = 1050.0,  # kg/m³
        temperature_c: float = 20.0
    ):
        """
        Initialize fractal floc properties calculator.

        Args:
            fractal_dimension: Fractal dimension Df (typically 1.8-2.5)
            primary_particle_diameter: Primary particle size d₀ [m]
            primary_particle_density: Primary particle density ρ_p [kg/m³]
            temperature_c: Water temperature [°C]
        """
        self.Df = fractal_dimension
        self.d0 = primary_particle_diameter
        self.rho_particle = primary_particle_density
        self.temperature_c = temperature_c

        # Water properties
        self.rho_water = calculate_water_density(temperature_c)
        self.mu_water = calculate_water_viscosity(temperature_c)
        self.nu_water = self.mu_water / self.rho_water  # Kinematic viscosity

    def effective_density(self, diameter: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Calculate effective density of fractal aggregate.

        Fractal scaling law:
        ρ_eff(d) = ρ_water + (ρ_particle - ρ_water) · (d/d₀)^(Df - 3)

        For Df < 3 (fractal aggregates), density decreases with size.
        For Df = 3 (compact spheres), density is constant.

        Args:
            diameter: Aggregate diameter [m]

        Returns:
            Effective density [kg/m³]

        Raises:
            ValueError: If diameter <= 0

        Note:
            Density is clamped to [ρ_water, ρ_particle] range to prevent
            unphysical values for extreme diameters.
        """
        # Guard against invalid diameters
        if np.any(diameter <= 0):
            raise ValueError("Diameter must be positive")

        # Fractal scaling exponent
        exponent = self.Df - 3.0

        # Density difference
        delta_rho = self.rho_particle - self.rho_water

        # Effective density
        rho_eff = self.rho_water + delta_rho * (diameter / self.d0)**exponent

        # Clamp to physical bounds [ρ_water, ρ_particle]
        rho_eff = np.clip(rho_eff, self.rho_water, self.rho_particle)

        return rho_eff

    def porosity(self, diameter: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Calculate porosity of fractal aggregate.

        Porosity ε = 1 - (d₀/d)^(3 - Df)

        Args:
            diameter: Aggregate diameter [m]

        Returns:
            Porosity (volume fraction voids) [-]

        Raises:
            ValueError: If diameter <= 0

        Note:
            Porosity is clamped to [0, 1] range to prevent unphysical values.
        """
        # Guard against invalid diameters
        if np.any(diameter <= 0):
            raise ValueError("Diameter must be positive")

        epsilon = 1.0 - (self.d0 / diameter)**(3.0 - self.Df)

        # Clamp to physical bounds [0, 1]
        epsilon = np.clip(epsilon, 0.0, 1.0)

        return epsilon


class FractalSettlingVelocity:
    """
    Calculate settling velocities for fractal aggregates using Stokes law
    with corrections for shape, porosity, and Reynolds number effects.
    """

    def __init__(
        self,
        floc_properties: FractalFlocProperties,
        shape_factor: float = 45.0 / 24.0  # Irregular floc vs sphere
    ):
        """
        Initialize settling velocity calculator.

        Args:
            floc_properties: FractalFlocProperties instance
            shape_factor: Shape correction K/24 (1.0 for spheres, 1.875 for irregular flocs)
        """
        self.floc_props = floc_properties
        self.phi = shape_factor

    def stokes_velocity(self, diameter: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Calculate settling velocity using modified Stokes law.

        For fractal aggregates with shape correction:
        v_s = (1/φ) · (g/18μ) · Δρ · d²

        where φ = shape factor (45/24 for irregular flocs, 1.0 for spheres)

        Valid for Re < 0.5 (laminar flow).

        Args:
            diameter: Aggregate diameter [m]

        Returns:
            Settling velocity [m/s] (positive = downward, zero if ρ_eff ≤ ρ_water)

        Note:
            If effective density ≤ water density (flotation regime), returns zero.
            Explicit flotation (upward velocity) should be handled separately.
        """
        # Effective density (varies with size for fractals)
        rho_eff = self.floc_props.effective_density(diameter)

        # Density difference driving settling
        delta_rho = rho_eff - self.floc_props.rho_water

        # Modified Stokes law with shape factor
        v_s = (1.0 / self.phi) * (GRAVITY / (18.0 * self.floc_props.mu_water)) * delta_rho * diameter**2

        # Clamp negative velocities to zero (flotation case)
        # Explicit flotation modeling should use separate DAF module
        v_s = np.maximum(v_s, 0.0)

        return v_s

    def reynolds_number(self, diameter: Union[float, np.ndarray], velocity: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Calculate particle Reynolds number.

        Re = v·d / ν

        Args:
            diameter: Particle diameter [m]
            velocity: Settling velocity [m/s]

        Returns:
            Reynolds number [-]
        """
        Re = velocity * diameter / self.floc_props.nu_water

        return Re

    def dietrich_velocity(self, diameter: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Calculate settling velocity using Dietrich (1982) formulation.

        Applicable for transitional and turbulent regimes (Re > 0.5).
        Uses dimensionless diameter D* and settling velocity w*.

        Args:
            diameter: Aggregate diameter [m]

        Returns:
            Settling velocity [m/s] (positive = downward, zero if ρ_eff ≤ ρ_water)

        Note:
            If effective density ≤ water density, returns zero.

        References:
            Dietrich (1982). Water Resources Research, 18(6), 1615-1626.
        """
        # Effective density
        rho_eff = self.floc_props.effective_density(diameter)
        delta_rho = rho_eff - self.floc_props.rho_water

        # Handle flotation case (ρ_eff ≤ ρ_water)
        is_scalar = np.isscalar(diameter)

        if np.any(delta_rho <= 0):
            # Return zero for flotation cases
            if is_scalar:
                return 0.0
            else:
                v_s = np.zeros_like(diameter)
                settling = delta_rho > 0
                if not np.any(settling):
                    return v_s
                # Process only settling particles
                delta_rho_subset = delta_rho[settling]
                diameter_subset = diameter[settling]
        else:
            # All particles settling
            delta_rho_subset = delta_rho
            diameter_subset = diameter

        # Dimensionless diameter
        R = delta_rho_subset / self.floc_props.rho_water
        D_star = diameter_subset * (R * GRAVITY / self.floc_props.nu_water**2)**(1.0/3.0)

        # Dietrich polynomial for dimensionless settling velocity
        # log10(w*) = a0 + a1·log10(D*) + a2·log10(D*)² + a3·log10(D*)³
        # Coefficients for natural particles (from Dietrich 1982, Table 2)
        a0 = -3.76715
        a1 = 1.92944
        a2 = -0.09815
        a3 = -0.00575

        log_D_star = np.log10(D_star)
        log_w_star = a0 + a1 * log_D_star + a2 * log_D_star**2 + a3 * log_D_star**3

        w_star = 10**log_w_star

        # Dimensional settling velocity
        v_s_local = w_star * (R * GRAVITY * self.floc_props.nu_water)**(1.0/3.0)

        if is_scalar:
            return v_s_local
        elif np.any(delta_rho <= 0):
            # Mixed case: fill in settling particles
            v_s[delta_rho > 0] = v_s_local
            return v_s
        else:
            # All settling
            return v_s_local

    def settling_velocity(
        self,
        diameter: Union[float, np.ndarray],
        re_threshold: float = 0.5
    ) -> Union[float, np.ndarray]:
        """
        Calculate settling velocity with automatic regime selection.

        Uses Stokes for Re < threshold, Dietrich for Re > threshold.

        Args:
            diameter: Aggregate diameter [m]
            re_threshold: Reynolds number threshold for regime switch

        Returns:
            Settling velocity [m/s]
        """
        # Try Stokes first
        v_stokes = self.stokes_velocity(diameter)
        Re = self.reynolds_number(diameter, v_stokes)

        # Check if Stokes is valid
        is_scalar = np.isscalar(diameter)

        if is_scalar:
            if Re < re_threshold:
                return v_stokes
            else:
                return self.dietrich_velocity(diameter)
        else:
            # Vectorized case
            v_s = np.zeros_like(diameter)
            laminar = Re < re_threshold

            v_s[laminar] = v_stokes[laminar]
            v_s[~laminar] = self.dietrich_velocity(diameter[~laminar])

            return v_s

    def settling_flux(
        self,
        diameter: Union[float, np.ndarray],
        concentration: Union[float, np.ndarray]
    ) -> Union[float, np.ndarray]:
        """
        Calculate solids settling flux.

        Flux = concentration × settling_velocity

        Args:
            diameter: Aggregate diameter [m]
            concentration: Solids concentration [kg/m³]

        Returns:
            Settling flux [kg/(m²·s)]
        """
        v_s = self.settling_velocity(diameter)
        flux = concentration * v_s

        return flux
