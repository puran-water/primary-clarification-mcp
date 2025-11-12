"""
Unit tests for Fractal Aggregate Settling Module.

Tests cover:
1. Fractal density scaling
2. Porosity calculations
3. Stokes settling velocity
4. Dietrich drag formulation
5. Reynolds number regime switching
6. Physical constraints and edge cases
"""

import pytest
import numpy as np
from utils.fractal_settling import (
    FractalFlocProperties,
    FractalSettlingVelocity,
    calculate_water_density,
    calculate_water_viscosity
)


class TestWaterProperties:
    """Test temperature-dependent water properties."""

    def test_water_density_at_20C(self):
        """Test water density at 20°C matches literature."""
        rho = calculate_water_density(20.0)
        # Literature: ρ(20°C) ≈ 998 kg/m³
        assert 997 < rho < 999

    def test_water_density_decreases_with_temperature(self):
        """Test ρ ↓ as T ↑."""
        rho_cold = calculate_water_density(4.0)
        rho_hot = calculate_water_density(30.0)

        assert rho_hot < rho_cold

    def test_water_viscosity_at_20C(self):
        """Test viscosity at 20°C matches literature."""
        mu = calculate_water_viscosity(20.0)
        # Literature: μ(20°C) ≈ 1.002 mPa·s
        assert 0.95e-3 < mu < 1.05e-3

    def test_water_viscosity_decreases_with_temperature(self):
        """Test μ ↓ as T ↑."""
        mu_cold = calculate_water_viscosity(5.0)
        mu_hot = calculate_water_viscosity(35.0)

        assert mu_hot < mu_cold


class TestFractalFlocProperties:
    """Test fractal floc property calculations."""

    def create_floc_properties(self):
        """Create standard fractal floc properties."""
        return FractalFlocProperties(
            fractal_dimension=2.3,
            primary_particle_diameter=1e-6,  # 1 μm
            primary_particle_density=1050.0,  # kg/m³
            temperature_c=20.0
        )

    def test_initialization(self):
        """Test proper initialization."""
        floc = self.create_floc_properties()

        assert floc.Df == 2.3
        assert floc.d0 == 1e-6
        assert floc.rho_particle == 1050.0
        assert 997 < floc.rho_water < 999

    def test_effective_density_decreases_with_size(self):
        """Test ρ_eff ↓ as d ↑ for fractal aggregates (Df < 3)."""
        floc = self.create_floc_properties()

        d_small = 10e-6  # 10 μm
        d_large = 100e-6  # 100 μm

        rho_small = floc.effective_density(d_small)
        rho_large = floc.effective_density(d_large)

        # For Df < 3, larger aggregates are less dense
        assert rho_large < rho_small
        assert rho_large > floc.rho_water  # Still denser than water

    def test_effective_density_at_primary_size(self):
        """Test ρ_eff = ρ_particle at d = d₀."""
        floc = self.create_floc_properties()

        rho_eff = floc.effective_density(floc.d0)

        # At primary particle size, should equal primary density
        assert np.isclose(rho_eff, floc.rho_particle, rtol=1e-10)

    def test_effective_density_for_compact_spheres(self):
        """Test ρ_eff = constant for Df = 3 (compact spheres)."""
        floc = FractalFlocProperties(
            fractal_dimension=3.0,  # Compact sphere
            primary_particle_diameter=1e-6,
            primary_particle_density=1050.0
        )

        d1 = 10e-6
        d2 = 100e-6

        rho1 = floc.effective_density(d1)
        rho2 = floc.effective_density(d2)

        # For Df = 3, density should be constant
        assert np.isclose(rho1, rho2, rtol=1e-10)
        assert np.isclose(rho1, floc.rho_particle, rtol=1e-10)

    def test_porosity_increases_with_size(self):
        """Test ε ↑ as d ↑ for fractal aggregates."""
        floc = self.create_floc_properties()

        d_small = 10e-6
        d_large = 100e-6

        eps_small = floc.porosity(d_small)
        eps_large = floc.porosity(d_large)

        # Larger aggregates are more porous
        assert eps_large > eps_small
        assert 0 < eps_large < 1

    def test_porosity_at_primary_size(self):
        """Test ε = 0 at d = d₀ (primary particle is solid)."""
        floc = self.create_floc_properties()

        eps = floc.porosity(floc.d0)

        assert np.isclose(eps, 0.0, atol=1e-10)

    def test_vectorized_operations(self):
        """Test vectorized density and porosity calculations."""
        floc = self.create_floc_properties()

        diameters = np.logspace(-6, -3, 10)  # 1 μm to 1 mm

        rho_eff = floc.effective_density(diameters)
        eps = floc.porosity(diameters)

        assert len(rho_eff) == len(diameters)
        assert len(eps) == len(diameters)

        # Check monotonicity
        assert np.all(np.diff(rho_eff) < 0)  # Density decreases
        assert np.all(np.diff(eps) > 0)  # Porosity increases


class TestFractalSettlingVelocity:
    """Test settling velocity calculations."""

    def create_settling_calculator(self):
        """Create standard settling velocity calculator."""
        floc_props = FractalFlocProperties(
            fractal_dimension=2.3,
            primary_particle_diameter=1e-6,
            primary_particle_density=1050.0,
            temperature_c=20.0
        )

        return FractalSettlingVelocity(
            floc_properties=floc_props,
            shape_factor=45.0 / 24.0  # Irregular floc
        )

    def test_stokes_velocity_increases_with_size(self):
        """Test v_s ↑ as d ↑ (for fixed density)."""
        calc = self.create_settling_calculator()

        d_small = 10e-6
        d_large = 50e-6

        v_small = calc.stokes_velocity(d_small)
        v_large = calc.stokes_velocity(d_large)

        # Larger particles settle faster (at fixed density)
        # Note: For fractals, density effect may partially offset this
        assert v_large > v_small

    def test_stokes_velocity_positive(self):
        """Test that settling velocities are positive."""
        calc = self.create_settling_calculator()

        diameters = np.logspace(-6, -4, 10)
        velocities = calc.stokes_velocity(diameters)

        assert np.all(velocities > 0)

    def test_reynolds_number_calculation(self):
        """Test Reynolds number calculation."""
        calc = self.create_settling_calculator()

        d = 100e-6  # 100 μm
        v = 1e-3  # 1 mm/s

        Re = calc.reynolds_number(d, v)

        # Re = v·d/ν ≈ 0.001 × 0.0001 / 1e-6 = 0.1
        assert 0.05 < Re < 0.15

    def test_dietrich_velocity_for_large_particles(self):
        """Test Dietrich formulation for larger particles."""
        calc = self.create_settling_calculator()

        d_large = 500e-6  # 500 μm

        v_dietrich = calc.dietrich_velocity(d_large)

        # Should be positive and reasonable (mm/s range)
        assert v_dietrich > 0
        assert v_dietrich < 0.1  # Less than 10 cm/s

    def test_regime_switching(self):
        """Test automatic switching between Stokes and Dietrich."""
        calc = self.create_settling_calculator()

        # Small particle (Stokes regime)
        d_small = 10e-6
        v_small = calc.settling_velocity(d_small, re_threshold=0.5)
        v_stokes_small = calc.stokes_velocity(d_small)

        # Should use Stokes
        assert np.isclose(v_small, v_stokes_small)

        # Large particle (may trigger Dietrich)
        d_large = 1000e-6  # 1 mm
        v_large = calc.settling_velocity(d_large, re_threshold=0.5)

        # Should be positive
        assert v_large > 0

    def test_vectorized_settling_velocity(self):
        """Test vectorized settling velocity calculations."""
        calc = self.create_settling_calculator()

        diameters = np.logspace(-6, -3, 20)  # 1 μm to 1 mm
        velocities = calc.settling_velocity(diameters)

        assert len(velocities) == len(diameters)
        assert np.all(velocities > 0)

    def test_settling_flux_calculation(self):
        """Test settling flux calculation."""
        calc = self.create_settling_calculator()

        d = 50e-6  # 50 μm
        C = 100.0  # kg/m³ concentration

        flux = calc.settling_flux(d, C)

        # Flux = C × v_s should be positive
        assert flux > 0

    def test_shape_factor_effect(self):
        """Test that shape factor affects settling velocity."""
        floc_props = FractalFlocProperties()

        # Spherical particles (φ = 1.0)
        calc_sphere = FractalSettlingVelocity(floc_props, shape_factor=1.0)

        # Irregular flocs (φ = 45/24 ≈ 1.875)
        calc_floc = FractalSettlingVelocity(floc_props, shape_factor=45.0/24.0)

        d = 50e-6

        v_sphere = calc_sphere.stokes_velocity(d)
        v_floc = calc_floc.stokes_velocity(d)

        # Irregular flocs settle slower (higher drag)
        assert v_floc < v_sphere

    def test_physical_bounds(self):
        """Test that settling velocities are physically reasonable."""
        calc = self.create_settling_calculator()

        # Range of floc sizes in primary clarifiers
        diameters = np.logspace(-6, -3, 50)  # 1 μm to 1 mm
        velocities = calc.settling_velocity(diameters)

        # All velocities should be:
        # 1. Positive
        assert np.all(velocities > 0)

        # 2. Less than terminal velocity of 1 cm spherical particle
        # (conservative upper bound)
        assert np.all(velocities < 0.1)  # 10 cm/s

        # 3. Greater than molecular diffusion (very slow)
        # Note: Very small fractal aggregates can settle extremely slowly
        assert np.all(velocities > 1e-9)  # 1 nm/s (conservative lower bound)


class TestFractalSettlingIntegration:
    """Test integration with realistic scenarios."""

    def test_wastewater_floc_settling(self):
        """Test settling of typical wastewater flocs."""
        # Typical primary clarifier flocs
        floc_props = FractalFlocProperties(
            fractal_dimension=2.4,  # Moderately bound flocs (more realistic)
            primary_particle_diameter=2e-6,  # 2 μm primaries
            primary_particle_density=1100.0,  # Organic-rich
            temperature_c=15.0  # Winter conditions
        )

        calc = FractalSettlingVelocity(floc_props)

        # Typical floc size range
        d = 100e-6  # 100 μm floc (typical range 50-200 μm)

        v_s = calc.settling_velocity(d)
        rho_eff = floc_props.effective_density(d)

        # Check reasonable values
        # For Df=2.4, loose flocs can have density very close to water
        assert 998 < rho_eff < 1100  # Density between water and particle (allow margin)
        assert 0.00001 < v_s < 0.01  # 0.01-10 mm/s range (broader for fractals)

    def test_temperature_effect_on_settling(self):
        """Test that temperature affects settling through viscosity."""
        # Cold water
        floc_cold = FractalFlocProperties(temperature_c=5.0)
        calc_cold = FractalSettlingVelocity(floc_cold)

        # Warm water
        floc_warm = FractalFlocProperties(temperature_c=25.0)
        calc_warm = FractalSettlingVelocity(floc_warm)

        d = 100e-6

        v_cold = calc_cold.stokes_velocity(d)
        v_warm = calc_warm.stokes_velocity(d)

        # Warmer water → lower viscosity → faster settling
        assert v_warm > v_cold

    def test_fractal_dimension_effect(self):
        """Test effect of fractal dimension on settling."""
        # Compact flocs (high Df)
        floc_compact = FractalFlocProperties(fractal_dimension=2.7)
        calc_compact = FractalSettlingVelocity(floc_compact)

        # Loose flocs (low Df)
        floc_loose = FractalFlocProperties(fractal_dimension=2.0)
        calc_loose = FractalSettlingVelocity(floc_loose)

        d = 100e-6

        v_compact = calc_compact.stokes_velocity(d)
        v_loose = calc_loose.stokes_velocity(d)

        # Compact flocs are denser → settle faster
        assert v_compact > v_loose


class TestBoundaryCases:
    """Test boundary cases and safety guardrails (Codex requirements)."""

    def test_negative_diameter_raises_error(self):
        """Test that negative diameter raises ValueError."""
        floc_props = FractalFlocProperties()

        with pytest.raises(ValueError, match="Diameter must be positive"):
            floc_props.effective_density(-1e-6)

        with pytest.raises(ValueError, match="Diameter must be positive"):
            floc_props.porosity(-1e-6)

    def test_zero_diameter_raises_error(self):
        """Test that zero diameter raises ValueError."""
        floc_props = FractalFlocProperties()

        with pytest.raises(ValueError, match="Diameter must be positive"):
            floc_props.effective_density(0.0)

        with pytest.raises(ValueError, match="Diameter must be positive"):
            floc_props.porosity(0.0)

    def test_effective_density_clamped_to_particle_density(self):
        """Test that ρ_eff doesn't exceed ρ_particle for small diameters."""
        floc_props = FractalFlocProperties(
            fractal_dimension=2.3,
            primary_particle_diameter=1e-6,
            primary_particle_density=1050.0
        )

        # For d < d₀, fractal power law would overshoot
        d_tiny = 0.1e-6  # 0.1 μm (smaller than d₀ = 1 μm)

        rho_eff = floc_props.effective_density(d_tiny)

        # Should be clamped to ρ_particle
        assert rho_eff <= floc_props.rho_particle
        assert np.isclose(rho_eff, floc_props.rho_particle)

    def test_effective_density_clamped_to_water_density(self):
        """Test that ρ_eff doesn't go below ρ_water for large diameters."""
        floc_props = FractalFlocProperties(
            fractal_dimension=2.0,  # Low Df → rapid density decay
            primary_particle_diameter=1e-6,
            primary_particle_density=1050.0
        )

        # For very large d with low Df, would undershoot
        d_huge = 10e-3  # 10 mm

        rho_eff = floc_props.effective_density(d_huge)

        # Should be clamped to ρ_water
        assert rho_eff >= floc_props.rho_water
        assert np.isclose(rho_eff, floc_props.rho_water, rtol=0.01)

    def test_porosity_clamped_to_zero(self):
        """Test that ε doesn't go negative for small diameters."""
        floc_props = FractalFlocProperties()

        d_tiny = 0.5e-6  # Smaller than d₀

        eps = floc_props.porosity(d_tiny)

        # Should be clamped to 0
        assert eps >= 0.0
        assert np.isclose(eps, 0.0)

    def test_porosity_clamped_to_one(self):
        """Test that ε doesn't exceed 1.0 for large diameters."""
        floc_props = FractalFlocProperties(
            fractal_dimension=1.8  # Very low Df
        )

        d_large = 1e-2  # 1 cm

        eps = floc_props.porosity(d_large)

        # Should be clamped to 1.0
        assert eps <= 1.0
        assert np.isclose(eps, 1.0, rtol=0.01)

    def test_flotation_case_returns_zero_velocity(self):
        """Test that particles with ρ_eff ≤ ρ_water return zero velocity."""
        # Create floc with density equal to water
        floc_props = FractalFlocProperties(
            fractal_dimension=2.0,
            primary_particle_diameter=1e-6,
            primary_particle_density=998.0  # Equal to water at 20°C
        )

        calc = FractalSettlingVelocity(floc_props)

        d = 100e-6

        # Stokes velocity should be zero
        v_stokes = calc.stokes_velocity(d)
        assert v_stokes == 0.0

        # Dietrich velocity should be zero
        v_dietrich = calc.dietrich_velocity(d)
        assert v_dietrich == 0.0

        # Settling velocity should be zero
        v_s = calc.settling_velocity(d)
        assert v_s == 0.0

    def test_flotation_case_vectorized(self):
        """Test flotation handling with mixed settling/floating particles."""
        # Create flocs with density gradient
        floc_props = FractalFlocProperties(
            fractal_dimension=2.0,  # Low Df → large particles approach ρ_water
            primary_particle_diameter=1e-6,
            primary_particle_density=1010.0  # Only slightly denser than water
        )

        calc = FractalSettlingVelocity(floc_props)

        # Mix of small (settling) and large (floating) particles
        diameters = np.array([10e-6, 100e-6, 1000e-6, 10000e-6])  # 10 μm to 1 cm

        velocities = calc.settling_velocity(diameters)

        # Small particles should settle (ρ_eff > ρ_water)
        assert velocities[0] > 0

        # Large particles may float (ρ_eff ≤ ρ_water) → zero velocity
        # All velocities should be non-negative
        assert np.all(velocities >= 0)

    def test_settling_flux_non_negative(self):
        """Test that settling flux is always non-negative."""
        calc = FractalSettlingVelocity(FractalFlocProperties())

        diameters = np.logspace(-6, -3, 20)
        concentrations = np.full_like(diameters, 100.0)  # 100 kg/m³

        fluxes = calc.settling_flux(diameters, concentrations)

        # All fluxes should be non-negative (downward or zero)
        assert np.all(fluxes >= 0)

    def test_vectorized_diameter_with_invalid_values(self):
        """Test array with some invalid diameters raises error."""
        floc_props = FractalFlocProperties()

        # Array with negative diameter
        diameters_negative = np.array([10e-6, -5e-6, 100e-6])

        with pytest.raises(ValueError, match="Diameter must be positive"):
            floc_props.effective_density(diameters_negative)

        # Array with zero diameter
        diameters_zero = np.array([10e-6, 0.0, 100e-6])

        with pytest.raises(ValueError, match="Diameter must be positive"):
            floc_props.porosity(diameters_zero)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
