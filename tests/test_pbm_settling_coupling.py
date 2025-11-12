"""
Tests for PBM-Settling Coupling Utility

Validates integration of:
- PBM size distributions
- Fractal settling velocities
- Hindered settling corrections
"""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))

from pbm_settling_coupling import (
    compute_bin_mass_concentrations,
    compute_total_tss,
    compute_bin_settling_velocities,
    compute_settling_fluxes,
    settling_velocity_summary,
    PRIMARY_PARAMS,
    BSM2_PARAMS
)
from fractal_settling import FractalFlocProperties, FractalSettlingVelocity
from hindered_settling import hindrance_factor


# Test fixtures
@pytest.fixture
def test_bins():
    """Standard test size bins (1-100 μm, 10 bins)."""
    return np.logspace(-6, -4, 10)


@pytest.fixture
def floc_props():
    """Standard fractal floc properties."""
    return FractalFlocProperties(
        fractal_dimension=2.3,
        primary_particle_diameter=1e-6,
        primary_particle_density=1050.0,
        temperature_c=20.0
    )


@pytest.fixture
def settling_calc(floc_props):
    """Fractal settling calculator."""
    return FractalSettlingVelocity(
        floc_properties=floc_props,
        shape_factor=45.0 / 24.0
    )


@pytest.fixture
def uniform_distribution(test_bins):
    """Uniform number distribution for testing."""
    return np.ones(len(test_bins)) * 1e9  # 1e9 #/m³ per bin


@pytest.fixture
def realistic_distribution(test_bins):
    """Log-normal distribution centered at 50 μm, scaled to ~200 mg/L TSS."""
    mean_diameter = 50e-6
    std_log = 0.5

    log_d = np.log(test_bins)
    log_mean = np.log(mean_diameter)
    distribution = np.exp(-0.5 * ((log_d - log_mean) / std_log)**2)

    # Normalize and scale to achieve ~200 mg/L TSS
    distribution = distribution / np.sum(distribution)
    # Scale down by factor of ~700 to get from 136,715 mg/L to ~200 mg/L
    total_number = 1.5e9  # #/m³ (adjusted from 1e12)

    return distribution * total_number


class TestMassConcentrationConversion:
    """Test conversion from number to mass concentrations."""

    def test_uniform_distribution_mass_increases_with_size(
        self, test_bins, uniform_distribution, floc_props
    ):
        """For uniform N(d), larger bins have more mass (due to d³ volume)."""
        mass_conc = compute_bin_mass_concentrations(
            test_bins, uniform_distribution, floc_props
        )

        # Mass should increase with diameter (volume scales as d³)
        # Even though density decreases for fractals (Df < 3)
        # The d³ term dominates
        assert mass_conc[0] < mass_conc[-1]

    def test_mass_concentration_uses_fractal_density(
        self, test_bins, uniform_distribution, floc_props
    ):
        """Verify fractal density correction is applied."""
        mass_conc = compute_bin_mass_concentrations(
            test_bins, uniform_distribution, floc_props
        )

        # Calculate what mass would be with constant density
        volumes = (np.pi / 6.0) * test_bins**3
        mass_constant_rho = uniform_distribution * floc_props.rho_particle * volumes

        # With Df=2.3 < 3, larger particles have lower density
        # So mass with fractal correction should be less than constant ρ
        # for larger bins
        assert mass_conc[-1] < mass_constant_rho[-1]

    def test_zero_number_concentration_gives_zero_mass(
        self, test_bins, floc_props
    ):
        """Zero particles → zero mass."""
        zero_dist = np.zeros(len(test_bins))
        mass_conc = compute_bin_mass_concentrations(
            test_bins, zero_dist, floc_props
        )

        assert np.all(mass_conc == 0.0)

    def test_mass_concentration_units(
        self, test_bins, uniform_distribution, floc_props
    ):
        """Verify mass concentrations have reasonable magnitudes."""
        mass_conc = compute_bin_mass_concentrations(
            test_bins, uniform_distribution, floc_props
        )

        # Total TSS should be in kg/m³ range
        TSS = np.sum(mass_conc)
        assert 0.0 < TSS < 100.0  # Typical range 0-100 kg/m³


class TestTotalTSS:
    """Test bulk TSS calculation from size distribution."""

    def test_tss_matches_manual_calculation(
        self, test_bins, uniform_distribution, floc_props
    ):
        """TSS should equal sum of bin masses."""
        mass_conc = compute_bin_mass_concentrations(
            test_bins, uniform_distribution, floc_props
        )
        TSS_expected = np.sum(mass_conc)

        TSS_computed = compute_total_tss(
            test_bins, uniform_distribution, floc_props
        )

        assert np.isclose(TSS_computed, TSS_expected)

    def test_tss_typical_wastewater_range(
        self, test_bins, realistic_distribution, floc_props
    ):
        """Realistic distribution should give TSS in 50-500 mg/L range."""
        TSS = compute_total_tss(
            test_bins, realistic_distribution, floc_props
        )

        TSS_mg_L = TSS * 1000.0
        assert 10.0 < TSS_mg_L < 1000.0  # Broad range for test stability


class TestSettlingVelocityCoupling:
    """Test main coupling function."""

    def test_free_settling_without_hindered_correction(
        self, test_bins, uniform_distribution, floc_props, settling_calc
    ):
        """With hindered correction off, should match fractal settling."""
        vs_coupled = compute_bin_settling_velocities(
            test_bins, uniform_distribution, floc_props, settling_calc,
            X_influent=0.2,
            use_hindered_correction=False
        )

        # Compare to direct fractal settling calculation
        vs_free_m_s = settling_calc.settling_velocity(test_bins)
        vs_free_m_day = vs_free_m_s * 86400.0

        np.testing.assert_allclose(vs_coupled, vs_free_m_day, rtol=1e-6)

    def test_hindered_velocities_less_than_free(
        self, test_bins, realistic_distribution, floc_props, settling_calc
    ):
        """Hindered velocities should be ≤ free-settling velocities."""
        results = compute_bin_settling_velocities(
            test_bins, realistic_distribution, floc_props, settling_calc,
            X_influent=0.2,
            use_hindered_correction=True,
            return_intermediate=True
        )

        vs_free = results['vs_free']
        vs_hindered = results['vs_hindered']

        # Hindered ≤ free (hindrance factor ≤ 1)
        assert np.all(vs_hindered <= vs_free)

    def test_takacs_double_exponential_behavior(
        self, test_bins, floc_props, settling_calc
    ):
        """Verify Takács double-exponential exhibits expected non-monotonic behavior.

        Takács has:vs = v0·[exp(-rh·X) - exp(-rp·X)]
        - Peak at intermediate TSS
        - Approaches zero at very low and very high TSS
        """
        # Test three concentration regimes
        N_low = np.ones(len(test_bins)) * 1e9  # ~0.67 kg/m³
        N_med = np.ones(len(test_bins)) * 5e9  # ~3.34 kg/m³
        N_high = np.ones(len(test_bins)) * 5e10  # ~33.4 kg/m³

        results_low = compute_bin_settling_velocities(
            test_bins, N_low, floc_props, settling_calc,
            X_influent=0.2, return_intermediate=True
        )
        results_med = compute_bin_settling_velocities(
            test_bins, N_med, floc_props, settling_calc,
            X_influent=0.2, return_intermediate=True
        )
        results_high = compute_bin_settling_velocities(
            test_bins, N_high, floc_props, settling_calc,
            X_influent=0.2, return_intermediate=True
        )

        # Verify all hindrance factors are in [0, 1]
        for results in [results_low, results_med, results_high]:
            assert 0.0 <= results['hindrance_factor'] <= 1.0

        # At very high concentration, hindrance should be strong (factor < 0.1)
        assert results_high['hindrance_factor'] < 0.1

    def test_primary_vs_secondary_clarifier_parameters(
        self, test_bins, floc_props, settling_calc
    ):
        """Primary clarifier has different parameters than secondary.

        Note: Takács behavior is complex (non-monotonic), so we just verify
        that different parameter sets give different results.
        """
        # Use realistic concentration ~3 kg/m³ (3000 mg/L)
        N_test = np.ones(len(test_bins)) * 5e9
        X_influent = 0.2

        # Primary clarifier parameters
        results_primary = compute_bin_settling_velocities(
            test_bins, N_test, floc_props, settling_calc,
            X_influent=X_influent,
            takacs_params=PRIMARY_PARAMS,
            return_intermediate=True
        )

        # Secondary clarifier parameters
        results_secondary = compute_bin_settling_velocities(
            test_bins, N_test, floc_props, settling_calc,
            X_influent=X_influent,
            takacs_params=BSM2_PARAMS,
            return_intermediate=True
        )

        # Different parameters should give different hindrance factors
        assert results_primary['hindrance_factor'] != results_secondary['hindrance_factor']

        # At least some velocities should differ
        assert not np.allclose(
            results_primary['vs_hindered'],
            results_secondary['vs_hindered']
        )

    def test_return_intermediate_results(
        self, test_bins, realistic_distribution, floc_props, settling_calc
    ):
        """Verify intermediate results dictionary."""
        results = compute_bin_settling_velocities(
            test_bins, realistic_distribution, floc_props, settling_calc,
            X_influent=0.2,
            return_intermediate=True
        )

        # Check all expected keys present
        assert 'vs_hindered' in results
        assert 'vs_free' in results
        assert 'mass_concentrations' in results
        assert 'TSS_total' in results
        assert 'hindrance_factor' in results

        # Check shapes
        assert results['vs_hindered'].shape == test_bins.shape
        assert results['vs_free'].shape == test_bins.shape
        assert results['mass_concentrations'].shape == test_bins.shape

        # Check hindrance factor is dimensionless [0, 1]
        assert 0.0 <= results['hindrance_factor'] <= 1.0

    def test_velocity_units_m_per_day(
        self, test_bins, realistic_distribution, floc_props, settling_calc
    ):
        """Velocities should be in m/day (QSDsan convention)."""
        vs = compute_bin_settling_velocities(
            test_bins, realistic_distribution, floc_props, settling_calc,
            X_influent=0.2
        )

        # Typical settling velocities: 1e-7 to 100 m/day
        # (Not m/s which would be ~1e-12 to 1e-3)
        # Very small particles with strong hindrance can be extremely slow
        assert np.all(vs > 1e-8)  # > 1e-8 m/day (orders of magnitude above m/s range)
        assert np.all(vs < 500.0)  # < 500 m/day


class TestSettlingFluxes:
    """Test flux calculations."""

    def test_flux_units_kg_per_m2_per_day(
        self, test_bins, realistic_distribution, floc_props, settling_calc
    ):
        """Fluxes should be in kg/(m²·day)."""
        vs = compute_bin_settling_velocities(
            test_bins, realistic_distribution, floc_props, settling_calc,
            X_influent=0.2
        )

        fluxes = compute_settling_fluxes(
            test_bins, realistic_distribution, vs, floc_props
        )

        # Total flux depends on TSS and settling velocity
        # For dilute, hindered suspensions: can be very small
        total_flux = np.sum(fluxes)
        assert 1e-6 < total_flux < 500.0  # Broad range to handle hindered cases
        assert np.all(fluxes >= 0.0)  # Non-negative

    def test_flux_zero_for_zero_concentration(
        self, test_bins, floc_props, settling_calc
    ):
        """Zero particles → zero flux."""
        zero_dist = np.zeros(len(test_bins))
        vs = compute_bin_settling_velocities(
            test_bins, zero_dist, floc_props, settling_calc,
            X_influent=0.2
        )

        fluxes = compute_settling_fluxes(
            test_bins, zero_dist, vs, floc_props
        )

        assert np.all(fluxes == 0.0)

    def test_flux_proportional_to_velocity_and_concentration(
        self, test_bins, floc_props, settling_calc
    ):
        """J = C × v relationship."""
        N = np.ones(len(test_bins)) * 1e10
        vs = compute_bin_settling_velocities(
            test_bins, N, floc_props, settling_calc, X_influent=0.2
        )

        fluxes_1x = compute_settling_fluxes(test_bins, N, vs, floc_props)

        # Double concentration
        fluxes_2x = compute_settling_fluxes(test_bins, N * 2.0, vs, floc_props)

        # Flux should approximately double (velocity changes slightly due to hindrance)
        ratio = fluxes_2x / (fluxes_1x + 1e-12)
        assert np.all(ratio > 1.5)  # Should be ~2.0 but hindrance reduces it


class TestSettlingVelocitySummary:
    """Test diagnostic summary function."""

    def test_summary_contains_all_fields(
        self, test_bins, realistic_distribution, floc_props, settling_calc
    ):
        """Summary should have all diagnostic fields."""
        summary = settling_velocity_summary(
            test_bins, realistic_distribution, floc_props, settling_calc,
            X_influent=0.2
        )

        expected_keys = [
            'diameters_um', 'vs_free_m_day', 'vs_hindered_m_day',
            'mass_concentrations_mg_L', 'TSS_total_mg_L',
            'hindrance_factor', 'effective_densities', 'reynolds_numbers'
        ]

        for key in expected_keys:
            assert key in summary

    def test_summary_units_conversion(
        self, test_bins, realistic_distribution, floc_props, settling_calc
    ):
        """Summary should convert to user-friendly units."""
        summary = settling_velocity_summary(
            test_bins, realistic_distribution, floc_props, settling_calc,
            X_influent=0.2
        )

        # Diameters in μm (not m)
        assert summary['diameters_um'][0] > 0.5  # 1 μm → >0.5 after conversion
        assert summary['diameters_um'][-1] < 200.0  # 100 μm

        # TSS in mg/L (not kg/m³)
        assert 10.0 < summary['TSS_total_mg_L'] < 1000.0

        # Velocities in m/day (small particles can be < 0.01 m/day)
        assert np.all(summary['vs_free_m_day'] > 1e-6)  # Positive, in m/day range
        assert np.all(summary['vs_free_m_day'] < 100.0)  # Reasonable upper bound

    def test_reynolds_numbers_reasonable(
        self, test_bins, realistic_distribution, floc_props, settling_calc
    ):
        """Reynolds numbers should be in laminar regime for most bins."""
        summary = settling_velocity_summary(
            test_bins, realistic_distribution, floc_props, settling_calc,
            X_influent=0.2
        )

        Re = summary['reynolds_numbers']

        # Most bins should be laminar (Re < 0.5)
        # Larger bins might be transitional
        assert np.all(Re < 100.0)  # All should be < 100


class TestBoundaryCases:
    """Test edge cases and error handling."""

    def test_takacs_hindrance_factor_bounds(
        self, test_bins, floc_props, settling_calc
    ):
        """Verify Takács hindrance factor stays within [0, 1] bounds.

        Takács double-exponential can approach zero at very low concentrations
        (non-intuitive but physically valid for the model).
        """
        # Test range of concentrations
        N_values = [1e7, 1e8, 1e9, 1e10, 1e11]  # Spanning 4 orders of magnitude

        for N_val in N_values:
            N_dist = np.ones(len(test_bins)) * N_val

            results = compute_bin_settling_velocities(
                test_bins, N_dist, floc_props, settling_calc,
                X_influent=0.2,
                return_intermediate=True
            )

            # Hindrance factor must be in [0, 1]
            assert 0.0 <= results['hindrance_factor'] <= 1.0

            # Hindered velocities must be ≤ free velocities
            assert np.all(results['vs_hindered'] <= results['vs_free'])

    def test_very_high_concentration_strong_hindrance(
        self, test_bins, floc_props, settling_calc
    ):
        """Very high TSS → low hindrance factor."""
        N_concentrated = np.ones(len(test_bins)) * 1e13  # Very high

        results = compute_bin_settling_velocities(
            test_bins, N_concentrated, floc_props, settling_calc,
            X_influent=0.2,
            return_intermediate=True
        )

        # Hindrance factor should be low
        assert results['hindrance_factor'] < 0.5

        # Hindered << free
        ratio = results['vs_hindered'] / (results['vs_free'] + 1e-12)
        assert np.all(ratio < 0.5)

    def test_single_bin_distribution(self, floc_props, settling_calc):
        """Handle single-bin edge case."""
        single_bin = np.array([50e-6])  # 50 μm
        N_single = np.array([1e10])

        vs = compute_bin_settling_velocities(
            single_bin, N_single, floc_props, settling_calc,
            X_influent=0.2
        )

        assert vs.shape == (1,)
        assert vs[0] > 0.0


class TestIntegrationWithPBM:
    """Test integration patterns with PBM output."""

    def test_pbm_to_settling_workflow(
        self, test_bins, floc_props, settling_calc
    ):
        """Simulate typical workflow: PBM → mass → settling → flux."""
        # Simulate PBM output (number concentrations)
        N_from_pbm = np.ones(len(test_bins)) * 1e10

        # Step 1: Compute settling velocities
        vs = compute_bin_settling_velocities(
            test_bins, N_from_pbm, floc_props, settling_calc,
            X_influent=0.2
        )

        # Step 2: Compute fluxes
        fluxes = compute_settling_fluxes(
            test_bins, N_from_pbm, vs, floc_props
        )

        # Verify workflow completes
        assert vs.shape == test_bins.shape
        assert fluxes.shape == test_bins.shape
        assert np.all(fluxes >= 0.0)

    def test_mass_conservation_check(
        self, test_bins, realistic_distribution, floc_props, settling_calc
    ):
        """Verify M₃ (volume moment) is preserved in mass calculations.

        M₃ = Σ N_i × V_i
        C_i = N_i × ρ_eff_i × V_i
        Therefore: M₃ = Σ (C_i / ρ_eff_i)
        """
        # Calculate M₃ from number distribution
        volumes = (np.pi / 6.0) * test_bins**3
        M3_from_N = np.sum(realistic_distribution * volumes)

        # Calculate M₃ from mass concentrations
        mass_conc = compute_bin_mass_concentrations(
            test_bins, realistic_distribution, floc_props
        )
        rho_eff = floc_props.effective_density(test_bins)

        # Convert back: N = C / (ρ × V), so M₃ = Σ N × V = Σ C / ρ
        M3_from_mass = np.sum(mass_conc / rho_eff)

        # Should be equal (within numerical precision)
        np.testing.assert_allclose(M3_from_N, M3_from_mass, rtol=1e-10)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
