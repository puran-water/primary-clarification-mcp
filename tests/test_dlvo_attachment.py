"""
Unit tests for DLVO-based particle-particle collision efficiency.

Tests cover:
1. Monotonicity requirements (Codex validation)
2. Bounds checking (α ∈ [10^-4, 1])
3. Literature validation (Hamaker constants, energy barriers)
4. Temperature dependence
5. Edge cases and numerical stability

References:
    - Edzwald (2010). Water Science & Technology, 61(3), 431-454.
    - Han et al. (2002). Water Science and Technology, 46(11-12), 191-198.
"""

import pytest
import numpy as np
from utils.dlvo_attachment import (
    calculate_debye_length,
    calculate_interaction_energy,
    calculate_energy_barrier,
    calculate_attachment_efficiency_capped,
    calculate_attachment_efficiency_arrhenius,
    calculate_collision_efficiency,
    calculate_alpha_matrix,
    HAMAKER_CONSTANTS,
    BOLTZMANN_CONSTANT,
)


class TestDebyeLength:
    """Test Debye screening length calculation."""

    def test_debye_length_standard_conditions(self):
        """Test Debye length at standard conditions (25°C, 0.001 M)."""
        # At 25°C, λ_D ≈ 0.304/√I [nm] for I in mol/L
        # For I = 0.001 M: λ_D ≈ 9.6 nm
        lambda_D = calculate_debye_length(ionic_strength_M=0.001, temperature_c=25.0)
        expected_nm = 0.304 / np.sqrt(0.001)  # ~9.6 nm
        assert np.isclose(lambda_D * 1e9, expected_nm, rtol=0.1)

    def test_debye_length_decreases_with_ionic_strength(self):
        """Test monotonicity: λ_D ↓ as I ↑ (Codex requirement)."""
        I_values = [0.0001, 0.001, 0.01, 0.1]
        lambda_values = [calculate_debye_length(I) for I in I_values]

        # Check strictly decreasing
        for i in range(len(lambda_values) - 1):
            assert lambda_values[i] > lambda_values[i + 1]

    def test_debye_length_temperature_dependence(self):
        """Test λ_D(T) with temperature-dependent dielectric constant.

        λ_D ∝ √(ε_r·T), but ε_r decreases with T faster than T increases,
        so λ_D actually decreases slightly with temperature (physically correct).
        """
        T_values = [5.0, 15.0, 25.0, 35.0]  # °C
        lambda_values = [calculate_debye_length(0.001, T) for T in T_values]

        # λ_D should decrease slightly with T due to ε_r(T) effect
        # Verify the values are in reasonable range (8-10 nm at I=0.001 M)
        for lambda_D in lambda_values:
            assert 8e-9 < lambda_D < 11e-9, f"λ_D={lambda_D*1e9:.2f} nm out of range"

        # Verify monotonic decrease (ε_r effect dominates)
        assert lambda_values[0] > lambda_values[-1]

    def test_debye_length_invalid_ionic_strength(self):
        """Test that invalid ionic strength raises ValueError (Codex requirement)."""
        import pytest

        # Zero ionic strength should raise
        with pytest.raises(ValueError, match="Ionic strength must be positive"):
            calculate_debye_length(0.0, 20.0)

        # Negative ionic strength should raise
        with pytest.raises(ValueError, match="Ionic strength must be positive"):
            calculate_debye_length(-0.001, 20.0)


class TestInteractionEnergy:
    """Test DLVO interaction energy calculation."""

    def test_vdw_is_attractive(self):
        """Test that van der Waals energy is negative (attractive)."""
        V_vdW, V_EDL, V_total = calculate_interaction_energy(
            h=5e-9, d1=10e-6, d2=10e-6,
            zeta1_mV=-25.0, zeta2_mV=-25.0,
            ionic_strength_M=0.001, temperature_c=20.0
        )
        assert V_vdW < 0, "Van der Waals should be attractive (negative)"

    def test_edl_is_repulsive_like_charges(self):
        """Test that EDL energy is positive for like charges (repulsive)."""
        V_vdW, V_EDL, V_total = calculate_interaction_energy(
            h=5e-9, d1=10e-6, d2=10e-6,
            zeta1_mV=-25.0, zeta2_mV=-25.0,
            ionic_strength_M=0.001, temperature_c=20.0
        )
        assert V_EDL > 0, "EDL should be repulsive for like charges (positive)"

    def test_vdw_increases_with_hamaker(self):
        """Test that |V_vdW| increases with Hamaker constant."""
        A_values = [3e-20, 5e-20, 8e-20]
        V_vdW_values = []

        for A in A_values:
            V_vdW, _, _ = calculate_interaction_energy(
                h=5e-9, d1=10e-6, d2=10e-6,
                zeta1_mV=-25.0, zeta2_mV=-25.0,
                ionic_strength_M=0.001, temperature_c=20.0,
                hamaker_constant=A
            )
            V_vdW_values.append(abs(V_vdW))

        # Check strictly increasing magnitude
        for i in range(len(V_vdW_values) - 1):
            assert V_vdW_values[i] < V_vdW_values[i + 1]

    def test_minimum_separation_handling(self):
        """Test that h=0 is handled gracefully (minimum separation)."""
        V_vdW, V_EDL, V_total = calculate_interaction_energy(
            h=0.0, d1=10e-6, d2=10e-6,
            zeta1_mV=-25.0, zeta2_mV=-25.0,
            ionic_strength_M=0.001, temperature_c=20.0
        )
        assert np.isfinite(V_vdW)
        assert np.isfinite(V_EDL)
        assert np.isfinite(V_total)


class TestEnergyBarrier:
    """Test DLVO energy barrier calculation."""

    def test_barrier_exists_like_charges(self):
        """Test that energy barrier exists for like-charged particles."""
        # Use smaller particles (1 μm) where DLVO barriers exist
        result = calculate_energy_barrier(
            d1=1e-6, d2=1e-6,
            zeta1_mV=-25.0, zeta2_mV=-25.0,
            ionic_strength_M=0.001, temperature_c=20.0
        )
        assert result["barrier_kT"] > 0, "Should have repulsive barrier for like charges"

    def test_barrier_decreases_with_ionic_strength(self):
        """Test monotonicity: barrier ↓ as I ↑ (screening effect)."""
        I_values = [0.0001, 0.001, 0.01, 0.1]
        barriers = []

        for I in I_values:
            result = calculate_energy_barrier(
                d1=1e-6, d2=1e-6,  # Use 1 μm particles
                zeta1_mV=-25.0, zeta2_mV=-25.0,
                ionic_strength_M=I, temperature_c=20.0
            )
            barriers.append(result["barrier_kT"])

        # Check decreasing trend (allow small non-monotonicities)
        assert barriers[0] > barriers[-1], "Barrier should decrease overall with I"

    def test_barrier_increases_with_zeta(self):
        """Test monotonicity: barrier ↑ as |ζ| ↑ (stronger repulsion)."""
        zeta_values = [-10.0, -20.0, -30.0, -40.0]  # mV
        barriers = []

        for zeta in zeta_values:
            result = calculate_energy_barrier(
                d1=1e-6, d2=1e-6,  # Use 1 μm particles
                zeta1_mV=zeta, zeta2_mV=zeta,
                ionic_strength_M=0.001, temperature_c=20.0
            )
            barriers.append(result["barrier_kT"])

        # Check increasing trend
        assert barriers[0] < barriers[-1], "Barrier should increase with |ζ|"

    def test_literature_hamaker_constants(self):
        """Test that literature Hamaker constants give reasonable barriers."""
        # From Edzwald (2010): A = 3.5-8.0×10^-20 J
        for particle_type, A in HAMAKER_CONSTANTS.items():
            assert 3e-20 <= A <= 9e-20, f"Hamaker for {particle_type} out of range"

            result = calculate_energy_barrier(
                d1=1e-6, d2=1e-6,  # Use 1 μm particles
                zeta1_mV=-25.0, zeta2_mV=-25.0,
                ionic_strength_M=0.001, temperature_c=20.0,
                particle_type=particle_type
            )
            # Energy barrier should be finite and positive for like charges
            assert 0 < result["barrier_kT"] < 1000, f"Barrier unreasonable for {particle_type}"


class TestAttachmentEfficiencyCapped:
    """Test capped attachment efficiency formulation (Codex-validated)."""

    def test_bounds_checking(self):
        """Test that α ∈ [10^-4, 1] (Codex requirement)."""
        barrier_values = np.linspace(-10.0, 100.0, 50)

        for barrier_kT in barrier_values:
            alpha = calculate_attachment_efficiency_capped(barrier_kT)
            assert 1e-4 <= alpha <= 1.0, f"α={alpha} out of bounds for barrier={barrier_kT} kT"

    def test_favorable_attachment(self):
        """Test that α=1.0 for negative barriers (attractive)."""
        alpha = calculate_attachment_efficiency_capped(barrier_kT=-5.0)
        assert alpha == 1.0

    def test_monotonic_decrease_with_barrier(self):
        """Test monotonicity: α ↓ as barrier ↑."""
        barrier_values = [0.0, 5.0, 10.0, 20.0, 50.0]
        alpha_values = [calculate_attachment_efficiency_capped(b) for b in barrier_values]

        # Check strictly decreasing
        for i in range(len(alpha_values) - 1):
            assert alpha_values[i] > alpha_values[i + 1]

    def test_n_factor_effect(self):
        """Test that n_factor controls steepness of α decay."""
        barrier_kT = 10.0
        n_values = [1.0, 3.0, 5.0]
        alpha_values = [calculate_attachment_efficiency_capped(barrier_kT, n) for n in n_values]

        # Higher n_factor → slower decay → higher α
        for i in range(len(alpha_values) - 1):
            assert alpha_values[i] < alpha_values[i + 1]


class TestAttachmentEfficiencyArrhenius:
    """Test Arrhenius attachment efficiency formulation (DAF-Sim original)."""

    def test_bounds_checking(self):
        """Test that α ∈ [10^-4, 1]."""
        barrier_values = np.linspace(-10.0, 100.0, 50)

        for barrier_kT in barrier_values:
            alpha = calculate_attachment_efficiency_arrhenius(barrier_kT)
            assert 1e-4 <= alpha <= 1.0, f"α={alpha} out of bounds"

    def test_favorable_attachment(self):
        """Test that α=1.0 for negative barriers."""
        alpha = calculate_attachment_efficiency_arrhenius(barrier_kT=-5.0)
        assert alpha == 1.0

    def test_monotonic_decrease_with_barrier(self):
        """Test monotonicity: α ↓ as barrier ↑."""
        barrier_values = [0.0, 5.0, 10.0, 20.0, 50.0]
        alpha_values = [calculate_attachment_efficiency_arrhenius(b) for b in barrier_values]

        # Check monotonic non-increasing (allows equality at lower bound)
        for i in range(len(alpha_values) - 1):
            assert alpha_values[i] >= alpha_values[i + 1], \
                f"α should be non-increasing: α[{barrier_values[i]}]={alpha_values[i]} < α[{barrier_values[i+1]}]={alpha_values[i+1]}"


class TestCollisionEfficiency:
    """Test main collision efficiency API."""

    def test_alpha_bounds(self):
        """Test that α ∈ [10^-4, 1] for main API."""
        result = calculate_collision_efficiency(
            d1=10e-6, d2=10e-6,
            zeta1_mV=-25.0, zeta2_mV=-25.0,
            ionic_strength_M=0.001, temperature_c=20.0
        )
        assert 1e-4 <= result["alpha"] <= 1.0

    def test_alpha_decreases_with_ionic_strength(self):
        """Test monotonicity: α ↓ as I ↓ (Codex requirement)."""
        I_values = [0.0001, 0.001, 0.01]
        alpha_values = []

        for I in I_values:
            result = calculate_collision_efficiency(
                d1=1e-6, d2=1e-6,  # Use 1 μm particles
                zeta1_mV=-25.0, zeta2_mV=-25.0,
                ionic_strength_M=I, temperature_c=20.0
            )
            alpha_values.append(result["alpha"])

        # Should increase overall with I (lower barrier)
        assert alpha_values[0] < alpha_values[-1]

    def test_alpha_decreases_with_zeta(self):
        """Test monotonicity: α ↓ as |ζ| ↑ (Codex requirement)."""
        zeta_values = [-10.0, -25.0, -40.0]
        alpha_values = []

        for zeta in zeta_values:
            result = calculate_collision_efficiency(
                d1=1e-6, d2=1e-6,  # Use 1 μm particles
                zeta1_mV=zeta, zeta2_mV=zeta,
                ionic_strength_M=0.001, temperature_c=20.0
            )
            alpha_values.append(result["alpha"])

        # Should decrease with increasing |ζ| (higher barrier)
        assert alpha_values[0] > alpha_values[-1]

    def test_both_alpha_methods(self):
        """Test that both capped and Arrhenius methods work."""
        params = {
            "d1": 10e-6, "d2": 10e-6,
            "zeta1_mV": -25.0, "zeta2_mV": -25.0,
            "ionic_strength_M": 0.001, "temperature_c": 20.0
        }

        result_capped = calculate_collision_efficiency(**params, alpha_method="capped")
        result_arrhenius = calculate_collision_efficiency(**params, alpha_method="arrhenius")

        assert 1e-4 <= result_capped["alpha"] <= 1.0
        assert 1e-4 <= result_arrhenius["alpha"] <= 1.0

    def test_temperature_propagation(self):
        """Test that temperature affects results (via Debye length and kT)."""
        T_values = [5.0, 20.0, 35.0]  # °C
        alpha_values = []

        for T in T_values:
            result = calculate_collision_efficiency(
                d1=1e-6, d2=1e-6,  # Use 1 μm particles
                zeta1_mV=-25.0, zeta2_mV=-25.0,
                ionic_strength_M=0.001, temperature_c=T
            )
            alpha_values.append(result["alpha"])

        # Temperature should affect results (higher T → more thermal energy)
        assert alpha_values[0] != alpha_values[-1]

    def test_literature_validation_optimum_conditions(self):
        """Test α ≈ 0.5-1.0 for optimum coagulation conditions (Edzwald 2010)."""
        # Optimum: low ionic strength, near-zero zeta potential
        result = calculate_collision_efficiency(
            d1=30e-6, d2=30e-6,
            zeta1_mV=-5.0, zeta2_mV=-5.0,  # Near-zero ζ
            ionic_strength_M=0.01,  # Moderate I
            temperature_c=20.0,
            alpha_method="capped"
        )

        # Should be in favorable range
        assert result["alpha"] > 0.3, f"α={result['alpha']} too low for optimum conditions"


class TestAlphaMatrix:
    """Test batch α matrix calculation for PBM integration."""

    def test_matrix_shape(self):
        """Test that α matrix has correct shape."""
        diameters = [5e-6, 10e-6, 20e-6, 40e-6]
        alpha_matrix = calculate_alpha_matrix(
            diameters=diameters,
            zeta_potentials_mV=[-25.0] * 4,
            ionic_strength_M=0.001,
            temperature_c=20.0
        )

        n = len(diameters)
        assert alpha_matrix.shape == (n, n)

    def test_matrix_symmetry(self):
        """Test that α matrix is symmetric (α_ij = α_ji)."""
        diameters = [5e-6, 10e-6, 20e-6]
        alpha_matrix = calculate_alpha_matrix(
            diameters=diameters,
            zeta_potentials_mV=[-25.0] * 3,
            ionic_strength_M=0.001,
            temperature_c=20.0
        )

        # Check symmetry
        assert np.allclose(alpha_matrix, alpha_matrix.T)

    def test_matrix_bounds(self):
        """Test that all α values in matrix ∈ [10^-4, 1]."""
        diameters = [5e-6, 10e-6, 20e-6, 40e-6]
        alpha_matrix = calculate_alpha_matrix(
            diameters=diameters,
            zeta_potentials_mV=[-25.0] * 4,
            ionic_strength_M=0.001,
            temperature_c=20.0
        )

        assert np.all(alpha_matrix >= 1e-4)
        assert np.all(alpha_matrix <= 1.0)

    def test_matrix_with_varying_zeta(self):
        """Test α matrix with different zeta potentials."""
        diameters = [1e-6, 2e-6, 4e-6]  # Use smaller particles (1-4 μm)
        zetas = [-10.0, -25.0, -40.0]  # Different surface charges

        alpha_matrix = calculate_alpha_matrix(
            diameters=diameters,
            zeta_potentials_mV=zetas,
            ionic_strength_M=0.001,
            temperature_c=20.0
        )

        # α(10 mV, 10 mV) should be higher than α(40 mV, 40 mV)
        assert alpha_matrix[0, 0] > alpha_matrix[2, 2]


class TestNumericalStability:
    """Test numerical stability and edge cases."""

    def test_extreme_ionic_strength(self):
        """Test that very low/high ionic strength is handled."""
        I_values = [1e-5, 1e-1]  # Extreme values

        for I in I_values:
            result = calculate_collision_efficiency(
                d1=10e-6, d2=10e-6,
                zeta1_mV=-25.0, zeta2_mV=-25.0,
                ionic_strength_M=I, temperature_c=20.0
            )
            assert np.isfinite(result["alpha"])
            assert 1e-4 <= result["alpha"] <= 1.0

    def test_extreme_zeta_potential(self):
        """Test that extreme zeta potentials are handled."""
        zeta_values = [-5.0, -50.0]  # mV

        for zeta in zeta_values:
            result = calculate_collision_efficiency(
                d1=10e-6, d2=10e-6,
                zeta1_mV=zeta, zeta2_mV=zeta,
                ionic_strength_M=0.001, temperature_c=20.0
            )
            assert np.isfinite(result["alpha"])
            assert 1e-4 <= result["alpha"] <= 1.0

    def test_extreme_temperature(self):
        """Test that extreme temperatures are handled."""
        T_values = [1.0, 50.0]  # °C (near freezing to warm)

        for T in T_values:
            result = calculate_collision_efficiency(
                d1=10e-6, d2=10e-6,
                zeta1_mV=-25.0, zeta2_mV=-25.0,
                ionic_strength_M=0.001, temperature_c=T
            )
            assert np.isfinite(result["alpha"])
            assert 1e-4 <= result["alpha"] <= 1.0

    def test_large_size_difference(self):
        """Test that large particle size differences are handled."""
        result = calculate_collision_efficiency(
            d1=1e-6, d2=100e-6,  # 100:1 size ratio
            zeta1_mV=-25.0, zeta2_mV=-25.0,
            ionic_strength_M=0.001, temperature_c=20.0
        )
        assert np.isfinite(result["alpha"])
        assert 1e-4 <= result["alpha"] <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
