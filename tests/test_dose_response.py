"""
Pytest tests for dose-response models.

Tests cover:
1. Ionic strength monotonicity with dose
2. Removal efficiency bounds and baseline behavior
3. Parameter preset regression
4. Hill function properties
"""

import pytest
import numpy as np
from utils.dose_response import (
    calculate_ionic_strength_from_dose,
    hill_function,
    tss_removal_dose_response,
    bod_removal_dose_response,
    get_parameter_set,
    PARAMETER_SETS
)


class TestIonicStrengthCalculation:
    """Test calculate_ionic_strength_from_dose() for monotonicity and correctness."""

    def test_monotonic_increase_al(self):
        """Ionic strength increases monotonically with Al dose."""
        doses = [0, 5, 10, 15, 20, 25]
        ionic_strengths = [calculate_ionic_strength_from_dose(dose_al_mg_l=d) for d in doses]

        # Check monotonic increase
        for i in range(1, len(ionic_strengths)):
            assert ionic_strengths[i] > ionic_strengths[i-1], \
                f"Ionic strength decreased from {ionic_strengths[i-1]:.4f} to {ionic_strengths[i]:.4f} at dose {doses[i]}"

    def test_monotonic_increase_fe(self):
        """Ionic strength increases monotonically with Fe dose."""
        doses = [0, 5, 10, 15, 20, 25]
        ionic_strengths = [calculate_ionic_strength_from_dose(dose_fe_mg_l=d) for d in doses]

        # Check monotonic increase
        for i in range(1, len(ionic_strengths)):
            assert ionic_strengths[i] > ionic_strengths[i-1]

    def test_mixed_dosing(self):
        """Ionic strength with mixed Fe+Al dosing."""
        i_fe_only = calculate_ionic_strength_from_dose(dose_fe_mg_l=10.0)
        i_al_only = calculate_ionic_strength_from_dose(dose_al_mg_l=10.0)
        i_mixed = calculate_ionic_strength_from_dose(dose_fe_mg_l=10.0, dose_al_mg_l=10.0)

        # Mixed should be greater than either alone
        assert i_mixed > i_fe_only
        assert i_mixed > i_al_only

    def test_zero_dose(self):
        """Zero dose returns only background ionic strength."""
        i_zero = calculate_ionic_strength_from_dose(dose_fe_mg_l=0, dose_al_mg_l=0)
        assert i_zero == 0.005  # Default background

    def test_background_contribution(self):
        """Background ionic strength is added to coagulant contribution."""
        i_low_bg = calculate_ionic_strength_from_dose(dose_al_mg_l=10.0, background_i_mol_l=0.001)
        i_high_bg = calculate_ionic_strength_from_dose(dose_al_mg_l=10.0, background_i_mol_l=0.010)

        assert i_high_bg > i_low_bg
        assert abs((i_high_bg - i_low_bg) - 0.009) < 1e-6


class TestHillFunction:
    """Test Hill function mathematical properties."""

    def test_bounds(self):
        """Hill function respects y_min and y_max bounds."""
        x_values = [0, 0.001, 0.01, 0.1, 1.0, 10.0, 100.0]
        y_min, y_max = 0.2, 0.9

        for x in x_values:
            y = hill_function(x, x_50=0.01, n=2.0, y_min=y_min, y_max=y_max)
            assert y_min <= y <= y_max, f"Hill function violated bounds at x={x}: y={y}"

    def test_baseline_at_zero(self):
        """Hill function returns y_min at x=0."""
        y = hill_function(x=0, x_50=0.01, n=2.0, y_min=0.6, y_max=0.9)
        assert y == 0.6

    def test_half_maximal(self):
        """Hill function returns midpoint at x=x_50."""
        y_min, y_max = 0.6, 0.9
        midpoint = (y_min + y_max) / 2
        y = hill_function(x=0.01, x_50=0.01, n=2.0, y_min=y_min, y_max=y_max)

        assert abs(y - midpoint) < 0.01  # Within 1%

    def test_monotonic_increase(self):
        """Hill function increases monotonically."""
        x_values = np.linspace(0, 0.05, 50)
        y_values = [hill_function(x, x_50=0.01, n=2.0, y_min=0.6, y_max=0.9) for x in x_values]

        for i in range(1, len(y_values)):
            assert y_values[i] >= y_values[i-1], f"Hill function decreased at index {i}"


class TestTSSRemovalDoseResponse:
    """Test TSS removal dose-response model."""

    def test_baseline_at_zero_dose(self):
        """Zero ionic strength returns baseline removal."""
        result = tss_removal_dose_response(
            ionic_strength_mol_l=0.0,
            baseline_removal=0.60,
            max_removal=0.90
        )

        assert abs(result['removal_efficiency'] - 0.60) < 0.01

    def test_max_removal_bound(self):
        """High ionic strength approaches max removal."""
        result = tss_removal_dose_response(
            ionic_strength_mol_l=1.0,  # Very high
            baseline_removal=0.60,
            max_removal=0.90
        )

        assert result['removal_efficiency'] < 0.90  # Should be close but not exceed
        assert result['removal_efficiency'] > 0.85  # Should be approaching max

    def test_monotonic_with_dose(self):
        """Removal increases monotonically with ionic strength."""
        i_values = [0.005, 0.007, 0.010, 0.015, 0.020]
        removals = [tss_removal_dose_response(ionic_strength_mol_l=i)['removal_efficiency']
                    for i in i_values]

        for i in range(1, len(removals)):
            assert removals[i] >= removals[i-1], f"Removal decreased at index {i}"

    def test_effluent_calculation(self):
        """Effluent TSS calculation is correct."""
        influent = 250.0
        result = tss_removal_dose_response(
            ionic_strength_mol_l=0.010,
            influent_tss_mg_l=influent
        )

        expected_effluent = influent * (1 - result['removal_efficiency'])
        assert abs(result['effluent_tss_mg_l'] - expected_effluent) < 0.1

    def test_negative_ionic_strength_raises(self):
        """Negative ionic strength raises ValueError."""
        with pytest.raises(ValueError, match="Ionic strength must be >= 0"):
            tss_removal_dose_response(ionic_strength_mol_l=-0.001)

    def test_invalid_bounds_raise(self):
        """Invalid removal bounds raise ValueError."""
        with pytest.raises(ValueError, match="Baseline removal must be 0-1"):
            tss_removal_dose_response(ionic_strength_mol_l=0.01, baseline_removal=1.5)

        with pytest.raises(ValueError, match="Max removal must be 0-1"):
            tss_removal_dose_response(ionic_strength_mol_l=0.01, max_removal=1.1)

        with pytest.raises(ValueError, match="Baseline removal .* > max removal"):
            tss_removal_dose_response(ionic_strength_mol_l=0.01,
                                     baseline_removal=0.8, max_removal=0.6)


class TestBODRemovalDoseResponse:
    """Test BOD removal dose-response model."""

    def test_particulate_follows_tss(self):
        """Particulate BOD removal tracks TSS removal."""
        tss_removal = 0.75
        result = bod_removal_dose_response(
            ionic_strength_mol_l=0.010,
            tss_removal_efficiency=tss_removal,
            particulate_fraction=0.70
        )

        assert result['pbod_removal_efficiency'] == tss_removal

    def test_soluble_limited(self):
        """Soluble BOD removal is limited even at high ionic strength."""
        result = bod_removal_dose_response(
            ionic_strength_mol_l=1.0,  # Very high
            influent_bod_mg_l=200,
            tss_removal_efficiency=0.90,
            particulate_fraction=0.70,
            max_removal_soluble=0.30
        )

        # sBOD removal should be < 30%
        assert result['sbod_removal_efficiency'] < 0.30

    def test_total_removal_calculation(self):
        """Total BOD removal is sum of pBOD and sBOD removal."""
        result = bod_removal_dose_response(
            ionic_strength_mol_l=0.010,
            influent_bod_mg_l=200,
            particulate_fraction=0.70
        )

        expected_total = result['pbod_removed_mg_l'] + result['sbod_removed_mg_l']
        assert abs(result['bod_removed_mg_l'] - expected_total) < 0.1


class TestParameterSets:
    """Test parameter preset regression."""

    def test_all_presets_exist(self):
        """All documented parameter sets exist."""
        expected = ["municipal_baseline", "industrial_high_tss", "cept_optimized"]
        for name in expected:
            assert name in PARAMETER_SETS, f"Missing parameter set: {name}"

    def test_get_parameter_set(self):
        """get_parameter_set returns valid parameters."""
        params = get_parameter_set("municipal_baseline")

        assert "tss" in params
        assert "bod" in params
        assert "description" in params

        # Check TSS parameters
        assert "baseline_removal" in params["tss"]
        assert "max_removal" in params["tss"]
        assert "i_50" in params["tss"]
        assert "hill_coef" in params["tss"]

    def test_parameter_values_regression(self):
        """Parameter values match expected (regression test)."""
        params = get_parameter_set("municipal_baseline")

        # TSS parameters
        assert params["tss"]["baseline_removal"] == 0.60
        assert params["tss"]["max_removal"] == 0.90
        assert params["tss"]["i_50"] == 0.010
        assert params["tss"]["hill_coef"] == 2.0

        # BOD parameters
        assert params["bod"]["particulate_fraction"] == 0.70

    def test_parameter_set_copy(self):
        """get_parameter_set returns a copy (not reference)."""
        params1 = get_parameter_set("municipal_baseline")
        params2 = get_parameter_set("municipal_baseline")

        params1["tss"]["baseline_removal"] = 0.99  # Modify copy

        # Original should be unchanged
        assert params2["tss"]["baseline_removal"] == 0.60

    def test_invalid_preset_raises(self):
        """Invalid preset name raises KeyError."""
        with pytest.raises(KeyError):
            get_parameter_set("nonexistent_preset")


if __name__ == "__main__":
    # Allow running pytest from this file directly
    pytest.main([__file__, "-v"])
