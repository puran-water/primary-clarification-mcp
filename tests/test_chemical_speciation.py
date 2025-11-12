"""
Pytest tests for chemical speciation (PHREEQC integration).

Tests cover:
1. Alkalinity feasibility checking
2. Safety clamps for precipitated metals
3. Dual ionic strength outputs
4. Stoichiometric P removal floors
"""

import pytest
from utils.chemical_speciation import (
    metal_speciation,
    check_alkalinity_feasibility,
    stoichiometric_p_removal_floor
)


class TestMetalSpeciation:
    """Test metal_speciation() function."""

    def test_no_dose_baseline(self):
        """No coagulant dose returns baseline chemistry."""
        result = metal_speciation(
            dose_fe_mg_l=0,
            dose_al_mg_l=0,
            ph_in=7.2,
            alkalinity_mg_l_caco3=150
        )

        # pH should be close to input
        assert abs(result['ph_out'] - 7.2) < 0.5

        # No metal hydroxides precipitated
        assert result['fe_precipitated_mg_l'] == 0
        assert result['al_precipitated_mg_l'] == 0
        assert result['total_hydroxide_mg_l'] == 0

    def test_dual_ionic_strengths_exposed(self):
        """Both pre-precipitation and equilibrium ionic strengths returned."""
        result = metal_speciation(
            dose_al_mg_l=10.0,
            influent_tp_mg_l=5.0
        )

        assert 'ionic_strength_mol_l' in result  # Pre-precipitation
        assert 'ionic_strength_equilibrium_mol_l' in result  # Equilibrium

        # Pre-precipitation should be >= equilibrium (metals precipitate out)
        assert result['ionic_strength_mol_l'] >= result['ionic_strength_equilibrium_mol_l'] * 0.9

    def test_precipitated_metals_non_negative(self):
        """Precipitated metal masses are always >= 0 (safety clamps)."""
        result = metal_speciation(
            dose_al_mg_l=5.0,
            dose_fe_mg_l=5.0,
            influent_tp_mg_l=5.0
        )

        assert result['fe_precipitated_mg_l'] >= 0
        assert result['al_precipitated_mg_l'] >= 0
        assert result['total_hydroxide_mg_l'] >= 0
        assert result['p_precipitated_mg_l'] >= 0

    def test_alkalinity_consumption(self):
        """Metal coagulants consume alkalinity."""
        result = metal_speciation(
            dose_al_mg_l=10.0,
            alkalinity_mg_l_caco3=150
        )

        # Alkalinity should be consumed
        assert result['alkalinity_consumed_meq_l'] > 0
        assert result['alkalinity_out_mg_l_caco3'] < 150

    def test_phosphorus_removal(self):
        """Metal coagulants precipitate phosphorus."""
        result = metal_speciation(
            dose_al_mg_l=10.0,
            influent_tp_mg_l=5.0
        )

        # Some P should be removed
        assert result['p_precipitated_mg_l'] > 0
        assert result['p_effluent_mg_l'] < 5.0

    def test_insufficient_alkalinity_raises(self):
        """Excessive dose with low alkalinity raises ValueError."""
        with pytest.raises(ValueError, match="Insufficient alkalinity"):
            metal_speciation(
                dose_al_mg_l=50.0,
                alkalinity_mg_l_caco3=20.0  # Way too low
            )

    def test_aluminum_precipitation(self):
        """Aluminum precipitates as hydroxide."""
        result = metal_speciation(
            dose_al_mg_l=15.0,
            influent_tp_mg_l=5.0,
            alkalinity_mg_l_caco3=150  # Sufficient alkalinity for dose
        )

        # Significant Al should precipitate
        assert result['al_precipitated_mg_l'] > 10.0

        # Gibbsite should form
        assert 'Gibbsite' in result['minerals_formed']

    def test_iron_precipitation(self):
        """Iron precipitates as hydroxide."""
        result = metal_speciation(
            dose_fe_mg_l=20.0,
            influent_tp_mg_l=5.0
        )

        # Significant Fe should precipitate
        assert result['fe_precipitated_mg_l'] > 15.0

        # Fe(OH)3(a) should form
        assert 'Fe(OH)3(a)' in result['minerals_formed']


class TestAlkalinityFeasibility:
    """Test check_alkalinity_feasibility() function."""

    def test_sufficient_alkalinity(self):
        """Adequate alkalinity passes feasibility check."""
        check = check_alkalinity_feasibility(
            dose_fe_mg_l=10.0,
            dose_al_mg_l=10.0,
            alkalinity_mg_l_caco3=200.0
        )

        assert check['feasible'] is True
        assert check['warning'] is None
        assert check['alkalinity_margin_mg_l'] > 0

    def test_insufficient_alkalinity(self):
        """Inadequate alkalinity fails feasibility check."""
        check = check_alkalinity_feasibility(
            dose_fe_mg_l=0,
            dose_al_mg_l=50.0,
            alkalinity_mg_l_caco3=80.0
        )

        assert check['feasible'] is False
        assert check['warning'] is not None
        assert check['alkalinity_margin_mg_l'] < 0

    def test_zero_dose(self):
        """Zero dose always feasible."""
        check = check_alkalinity_feasibility(
            dose_fe_mg_l=0,
            dose_al_mg_l=0,
            alkalinity_mg_l_caco3=50.0
        )

        assert check['feasible'] is True

    def test_mixed_dosing(self):
        """Mixed Fe+Al dosing alkalinity requirement."""
        check_fe = check_alkalinity_feasibility(
            dose_fe_mg_l=10.0,
            dose_al_mg_l=0,
            alkalinity_mg_l_caco3=100.0
        )
        check_al = check_alkalinity_feasibility(
            dose_fe_mg_l=0,
            dose_al_mg_l=10.0,
            alkalinity_mg_l_caco3=100.0
        )
        check_mixed = check_alkalinity_feasibility(
            dose_fe_mg_l=10.0,
            dose_al_mg_l=10.0,
            alkalinity_mg_l_caco3=100.0
        )

        # Mixed should require more than either alone
        total_required = (check_fe['alkalinity_required_mg_l'] +
                         check_al['alkalinity_required_mg_l'])
        assert check_mixed['alkalinity_required_mg_l'] == pytest.approx(total_required, rel=0.05)


class TestStoichiometricPRemoval:
    """Test stoichiometric_p_removal_floor() function."""

    def test_fe_stoichiometry(self):
        """Fe:P ratio is approximately 1.8:1."""
        p_in = 5.0
        fe_min = stoichiometric_p_removal_floor(p_in, metal_type="fe")

        expected = p_in * 1.8
        assert fe_min == pytest.approx(expected, rel=0.01)

    def test_al_stoichiometry(self):
        """Al:P ratio is approximately 0.87:1."""
        p_in = 5.0
        al_min = stoichiometric_p_removal_floor(p_in, metal_type="al")

        expected = p_in * 0.87
        assert al_min == pytest.approx(expected, rel=0.01)

    def test_fe_requires_more_mass(self):
        """Fe requires more mass than Al for same P removal."""
        p_in = 5.0
        fe_min = stoichiometric_p_removal_floor(p_in, "fe")
        al_min = stoichiometric_p_removal_floor(p_in, "al")

        assert fe_min > al_min

    def test_invalid_metal_type_raises(self):
        """Invalid metal type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown metal_type"):
            stoichiometric_p_removal_floor(5.0, metal_type="copper")

    def test_zero_phosphorus(self):
        """Zero phosphorus returns zero dose."""
        fe_min = stoichiometric_p_removal_floor(0.0, "fe")
        al_min = stoichiometric_p_removal_floor(0.0, "al")

        assert fe_min == 0.0
        assert al_min == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
