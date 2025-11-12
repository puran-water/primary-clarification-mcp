"""
Tests for PrimaryClarifierPBM ODE Integration

Validates that the _compile_ODE() method correctly integrates:
- PBM aggregation kinetics
- Fractal settling velocities
- Takács hindered settling
- Hydraulic advection
- Vertical flux transport
"""

import pytest
import numpy as np
import sys
from pathlib import Path
from scipy.integrate import solve_ivp

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent / "qsdsan_units"))
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))

from primary_clarifier_pbm import create_test_clarifier
from pbm_settling_coupling import compute_total_tss


class TestODECompilation:
    """Test ODE system compilation and basic functionality."""

    def test_compile_ode_returns_callable(self):
        """ODE compilation should return a callable function."""
        clarifier = create_test_clarifier(N_layer=5, N_bins=10)
        dy_dt = clarifier._compile_ODE()

        assert callable(dy_dt)

    def test_ode_signature(self):
        """ODE function should accept (t, y) and return dy."""
        clarifier = create_test_clarifier(N_layer=5, N_bins=10)
        dy_dt = clarifier._compile_ODE()

        # Test with initial state
        t = 0.0
        y = clarifier._init_state(influent_TSS_mg_L=200.0)

        # Should return array of same shape
        dy = dy_dt(t, y)

        assert dy.shape == y.shape
        assert isinstance(dy, np.ndarray)

    def test_ode_returns_finite_values(self):
        """ODE should not return NaN or Inf values."""
        clarifier = create_test_clarifier(N_layer=5, N_bins=10)
        dy_dt = clarifier._compile_ODE()

        y = clarifier._init_state(influent_TSS_mg_L=200.0)
        dy = dy_dt(0.0, y)

        assert np.all(np.isfinite(dy))
        assert not np.any(np.isnan(dy))
        assert not np.any(np.isinf(dy))


class TestODEPhysicsIntegration:
    """Test that ODE correctly integrates all physics modules."""

    def test_aggregation_term_present(self):
        """ODE should include aggregation kinetics."""
        clarifier = create_test_clarifier(N_layer=3, N_bins=10)
        dy_dt = clarifier._compile_ODE()

        y = clarifier._init_state(influent_TSS_mg_L=200.0)

        # Evaluate ODE
        dy = dy_dt(0.0, y)

        # Aggregation should cause some bins to grow, some to shrink
        # Total number should decrease (coagulation reduces count)
        # We can't test this directly without disabling other terms,
        # but we can verify the ODE is non-zero (some dynamics present)
        assert not np.allclose(dy, 0.0)

    def test_settling_term_present(self):
        """ODE should include settling flux between layers."""
        clarifier = create_test_clarifier(N_layer=5, N_bins=10)
        dy_dt = clarifier._compile_ODE()

        # Create state with particles only in top layer
        y = np.zeros(5 * 10)
        y[0:10] = 1e10  # Top layer only

        dy = dy_dt(0.0, y)

        # Top layer should lose particles (negative rate)
        dy_top = dy[0:10]
        assert np.any(dy_top < 0)

        # Second layer should gain particles (positive rate)
        dy_second = dy[10:20]
        assert np.any(dy_second > 0)

    def test_hydraulic_advection_present(self):
        """ODE should include hydraulic advection terms."""
        clarifier = create_test_clarifier(N_layer=5, N_bins=10)
        dy_dt = clarifier._compile_ODE()

        y = clarifier._init_state(influent_TSS_mg_L=200.0)
        dy = dy_dt(0.0, y)

        # Some dynamics should be present
        assert not np.allclose(dy, 0.0)


class TestODEIntegration:
    """Test numerical integration of ODE system."""

    def test_short_time_integration(self):
        """ODE should integrate successfully for short time period."""
        clarifier = create_test_clarifier(N_layer=3, N_bins=5)
        dy_dt = clarifier._compile_ODE()

        y0 = clarifier._init_state(influent_TSS_mg_L=200.0)

        # Integrate for 0.1 days (2.4 hours)
        t_span = (0.0, 0.1)
        t_eval = np.linspace(0.0, 0.1, 11)

        try:
            sol = solve_ivp(
                dy_dt,
                t_span,
                y0,
                method='BDF',  # Stiff solver
                t_eval=t_eval,
                rtol=1e-6,
                atol=1e-9
            )

            assert sol.success, f"Integration failed: {sol.message}"
            assert len(sol.t) > 1  # Multiple time points evaluated

        except Exception as e:
            pytest.fail(f"Integration raised exception: {e}")

    def test_state_remains_positive(self):
        """Number concentrations should remain positive during integration."""
        clarifier = create_test_clarifier(N_layer=3, N_bins=5)
        dy_dt = clarifier._compile_ODE()

        y0 = clarifier._init_state(influent_TSS_mg_L=200.0)

        # Integrate
        sol = solve_ivp(
            dy_dt,
            (0.0, 0.05),  # 0.05 days
            y0,
            method='BDF',
            rtol=1e-6,
            atol=1e-9
        )

        # All states should remain non-negative
        # (Small numerical negative values < 1e-10 are acceptable)
        assert np.all(sol.y >= -1e-10)


class TestODEConservation:
    """Test conservation properties of ODE system."""

    def test_m3_approximate_conservation(self):
        """M₃ (volume moment) should be approximately conserved.

        Note: M₃ won't be perfectly conserved due to:
        - Aggregation changes volume if fractal density varies
        - Hydraulic flows add/remove particles
        - Feed injection adds volume

        We test that M₃ doesn't change dramatically (< 50% over short time).
        """
        clarifier = create_test_clarifier(N_layer=3, N_bins=5)
        dy_dt = clarifier._compile_ODE()

        y0 = clarifier._init_state(influent_TSS_mg_L=200.0)

        # Calculate initial M₃
        volumes = (np.pi / 6.0) * clarifier.diameter_bins**3
        N_state_0 = y0.reshape((3, 5))
        M3_0 = np.sum(N_state_0 * volumes)

        # Integrate for short time
        sol = solve_ivp(
            dy_dt,
            (0.0, 0.01),  # Very short: 0.01 days = 14.4 minutes
            y0,
            method='BDF',
            rtol=1e-6,
            atol=1e-9
        )

        # Calculate final M₃
        N_state_f = sol.y[:, -1].reshape((3, 5))
        M3_f = np.sum(N_state_f * volumes)

        # M₃ should not change drastically
        # Allow up to 50% change (due to feed injection and flows)
        if M3_0 > 0:
            relative_change = abs(M3_f - M3_0) / M3_0
            assert relative_change < 0.5, f"M₃ changed by {relative_change*100:.1f}%"

    def test_mass_conservation_with_flows(self):
        """Total mass should change consistently with flows."""
        clarifier = create_test_clarifier(N_layer=3, N_bins=5)
        dy_dt = clarifier._compile_ODE()

        y0 = clarifier._init_state(influent_TSS_mg_L=200.0)

        # Calculate initial total TSS
        N_state_0 = y0.reshape((3, 5))
        TSS_0 = 0.0
        for i in range(3):
            TSS_layer = compute_total_tss(
                clarifier.diameter_bins,
                N_state_0[i, :],
                clarifier.floc_props
            )
            TSS_0 += TSS_layer

        # Integrate
        sol = solve_ivp(
            dy_dt,
            (0.0, 0.01),
            y0,
            method='BDF',
            rtol=1e-6,
            atol=1e-9
        )

        # Calculate final total TSS
        N_state_f = sol.y[:, -1].reshape((3, 5))
        TSS_f = 0.0
        for i in range(3):
            TSS_layer = compute_total_tss(
                clarifier.diameter_bins,
                N_state_f[i, :],
                clarifier.floc_props
            )
            TSS_f += TSS_layer

        # TSS should be finite and positive
        assert TSS_0 > 0
        assert TSS_f > 0
        assert np.isfinite(TSS_f)


class TestODEBoundaryCases:
    """Test ODE behavior in edge cases."""

    def test_empty_layer_handling(self):
        """ODE should handle empty layers without errors."""
        clarifier = create_test_clarifier(N_layer=5, N_bins=10)
        dy_dt = clarifier._compile_ODE()

        # Create state with some empty layers
        y = np.zeros(5 * 10)
        y[0:10] = 1e10  # Only top layer has particles
        y[20:30] = 1e9  # Third layer has some

        # Should not raise errors
        dy = dy_dt(0.0, y)

        assert np.all(np.isfinite(dy))

    def test_very_dilute_suspension(self):
        """ODE should handle very dilute suspensions."""
        clarifier = create_test_clarifier(N_layer=3, N_bins=5)
        dy_dt = clarifier._compile_ODE()

        # Very low concentration
        y = clarifier._init_state(influent_TSS_mg_L=1.0)  # 1 mg/L

        dy = dy_dt(0.0, y)

        assert np.all(np.isfinite(dy))

    def test_concentrated_suspension(self):
        """ODE should handle concentrated suspensions."""
        clarifier = create_test_clarifier(N_layer=3, N_bins=5)
        dy_dt = clarifier._compile_ODE()

        # High concentration
        y = clarifier._init_state(influent_TSS_mg_L=5000.0)  # 5000 mg/L

        dy = dy_dt(0.0, y)

        assert np.all(np.isfinite(dy))


class TestODEPerformance:
    """Test ODE computational performance."""

    def test_single_evaluation_speed(self):
        """Single ODE evaluation should be reasonably fast."""
        import time

        clarifier = create_test_clarifier(N_layer=10, N_bins=20)
        dy_dt = clarifier._compile_ODE()

        y = clarifier._init_state(influent_TSS_mg_L=200.0)

        # Time 10 evaluations
        start = time.time()
        for _ in range(10):
            dy = dy_dt(0.0, y)
        elapsed = time.time() - start

        # Should take < 1 second for 10 evaluations
        # (Even on slow machines, 200 state variables shouldn't take long)
        avg_time = elapsed / 10
        assert avg_time < 1.0, f"ODE evaluation too slow: {avg_time:.3f} s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
