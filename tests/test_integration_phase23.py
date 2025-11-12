"""
Pytest tests for Phase 2.3 integration: dose-response models with removal_efficiency.py

Tests cover:
1. Baseline TSS removal (no chemistry)
2. TSS removal with chemistry (dose-response)
3. Chemistry never degrades performance
4. Complete removal profile with chemistry
5. Different parameter sets
6. Edge cases (high dose, low HRT, extreme temperatures)
"""

import pytest
from utils.removal_efficiency import tss_removal_bsm2, calculate_removal_profile


class TestTSSRemovalBSM2Integration:
    """Test tss_removal_bsm2() function with dose-response integration."""

    def test_baseline_no_chemistry(self):
        """Baseline TSS removal without chemistry."""
        result = tss_removal_bsm2(
            HRT_hours=2.0,
            influent_TSS_mg_l=250.0
        )

        # Verify dict structure
        assert 'removal_efficiency' in result
        assert 'baseline_removal' in result
        assert 'chemically_enhanced_removal' in result
        assert 'ionic_strength_mol_l' in result
        assert 'enhancement_source' in result

        # Verify no chemistry enhancement
        assert result['enhancement_source'] == 'none'
        assert result['chemically_enhanced_removal'] is None
        assert result['ionic_strength_mol_l'] is None

        # Verify baseline equals final removal
        assert result['removal_efficiency'] == result['baseline_removal']

    def test_zero_dose_chemistry_dict(self):
        """Chemistry dict with zero doses should not activate enhancement."""
        result = tss_removal_bsm2(
            HRT_hours=2.0,
            influent_TSS_mg_l=250.0,
            chemistry={"dose_fe_mg_l": 0.0, "dose_al_mg_l": 0.0}
        )

        # Should behave same as no chemistry
        assert result['enhancement_source'] == 'none'
        assert result['chemically_enhanced_removal'] is None
        assert result['ionic_strength_mol_l'] is None

    def test_al_dosing_dose_response(self):
        """Aluminum dosing activates dose-response enhancement."""
        al_doses = [5, 10, 15, 20]
        previous_enhanced = None

        for al_dose in al_doses:
            result = tss_removal_bsm2(
                HRT_hours=2.0,
                influent_TSS_mg_l=250.0,
                chemistry={"dose_al_mg_l": al_dose}
            )

            # Verify dose-response activation
            assert result['enhancement_source'] == 'dose_response'
            assert result['chemically_enhanced_removal'] is not None
            assert result['ionic_strength_mol_l'] is not None
            assert result['ionic_strength_mol_l'] > 0

            # Verify monotonic increase with dose
            if previous_enhanced is not None:
                assert result['chemically_enhanced_removal'] >= previous_enhanced

            previous_enhanced = result['chemically_enhanced_removal']

    def test_fe_dosing_dose_response(self):
        """Iron dosing activates dose-response enhancement."""
        result = tss_removal_bsm2(
            HRT_hours=2.0,
            influent_TSS_mg_l=250.0,
            chemistry={"dose_fe_mg_l": 15.0}
        )

        # Verify dose-response activation
        assert result['enhancement_source'] == 'dose_response'
        assert result['chemically_enhanced_removal'] is not None
        assert result['ionic_strength_mol_l'] is not None

    def test_chemistry_never_degrades_performance(self):
        """Final removal always >= baseline removal."""
        for al_dose in [2, 5, 10, 15, 20, 30]:
            result = tss_removal_bsm2(
                HRT_hours=2.0,
                influent_TSS_mg_l=250.0,
                chemistry={"dose_al_mg_l": al_dose}
            )

            assert result['removal_efficiency'] >= result['baseline_removal'], \
                f"Final ({result['removal_efficiency']:.3f}) < baseline ({result['baseline_removal']:.3f}) at {al_dose} mg/L Al"

    def test_mixed_fe_al_dosing(self):
        """Mixed Fe + Al dosing."""
        result = tss_removal_bsm2(
            HRT_hours=2.0,
            influent_TSS_mg_l=250.0,
            chemistry={"dose_fe_mg_l": 10.0, "dose_al_mg_l": 5.0}
        )

        # Verify dose-response activation
        assert result['enhancement_source'] == 'dose_response'
        assert result['chemically_enhanced_removal'] is not None
        assert result['ionic_strength_mol_l'] is not None

        # Ionic strength should reflect both metals
        assert result['ionic_strength_mol_l'] > 0.007  # Higher than Al alone


class TestCalculateRemovalProfile:
    """Test calculate_removal_profile() function."""

    def test_profile_no_chemistry(self):
        """Removal profile without chemistry."""
        profile = calculate_removal_profile(
            HRT_hours=2.0,
            influent_tss_mg_l=280.0,
            influent_bod_mg_l=200.0
        )

        # Verify all parameters present
        assert 'TSS' in profile
        assert 'BOD' in profile
        assert 'COD' in profile
        assert 'TP' in profile
        assert 'oil_grease' in profile

        # Verify detailed breakdown
        assert 'TSS_baseline' in profile
        assert 'TSS_chemically_enhanced' in profile
        assert 'ionic_strength_mol_l' in profile

        # No chemistry, so no detailed BOD breakdown
        assert profile['TSS_chemically_enhanced'] is None
        assert profile['BOD_particulate_removal'] is None
        assert profile['BOD_soluble_removal'] is None
        assert profile['BOD_effluent_mg_l'] is None

    def test_profile_with_chemistry(self):
        """Removal profile with chemistry includes detailed breakdown."""
        profile = calculate_removal_profile(
            HRT_hours=2.0,
            influent_tss_mg_l=280.0,
            influent_bod_mg_l=200.0,
            chemistry={"dose_al_mg_l": 10.0}
        )

        # Verify TSS breakdown
        assert profile['TSS_chemically_enhanced'] is not None
        assert profile['ionic_strength_mol_l'] is not None

        # Verify BOD breakdown with chemistry
        assert profile['BOD_particulate_removal'] is not None
        assert profile['BOD_soluble_removal'] is not None
        assert profile['BOD_effluent_mg_l'] is not None

        # Verify BOD effluent calculation
        expected_effluent = 200.0 * (1 - profile['BOD'])
        assert abs(profile['BOD_effluent_mg_l'] - expected_effluent) < 0.5

    def test_different_parameter_sets(self):
        """Different parameter sets produce different results."""
        parameter_sets = ["municipal_baseline", "industrial_high_tss", "cept_optimized"]
        results = []

        for param_set in parameter_sets:
            profile = calculate_removal_profile(
                HRT_hours=2.0,
                influent_tss_mg_l=300.0,
                influent_bod_mg_l=220.0,
                chemistry={"dose_al_mg_l": 12.0, "parameter_set": param_set}
            )
            results.append(profile)

        # Industrial and CEPT should have higher removal than municipal
        assert results[1]['TSS'] > results[0]['TSS']  # industrial > municipal
        assert results[2]['TSS'] > results[0]['TSS']  # cept > municipal

    def test_profile_tp_removal_with_chemistry(self):
        """TP removal is enhanced with chemistry."""
        profile_no_chem = calculate_removal_profile(
            HRT_hours=2.0,
            influent_tss_mg_l=280.0,
            influent_bod_mg_l=200.0
        )

        profile_with_chem = calculate_removal_profile(
            HRT_hours=2.0,
            influent_tss_mg_l=280.0,
            influent_bod_mg_l=200.0,
            chemistry={"dose_al_mg_l": 10.0}
        )

        # TP removal should be much higher with chemistry
        assert profile_with_chem['TP'] > profile_no_chem['TP'] + 0.2  # At least 20% better

    def test_profile_oil_grease_with_chemistry(self):
        """Oil & grease removal is enhanced with chemistry."""
        profile_no_chem = calculate_removal_profile(
            HRT_hours=2.0,
            influent_tss_mg_l=280.0
        )

        profile_with_chem = calculate_removal_profile(
            HRT_hours=2.0,
            influent_tss_mg_l=280.0,
            chemistry={"dose_al_mg_l": 10.0}
        )

        # Oil & grease removal should be slightly enhanced
        assert profile_with_chem['oil_grease'] >= profile_no_chem['oil_grease']


class TestEdgeCases:
    """Test edge cases: high dose, low HRT, extreme temperatures."""

    def test_very_high_dose(self):
        """Very high coagulant dose (40 mg/L Al)."""
        result = tss_removal_bsm2(
            HRT_hours=2.0,
            influent_TSS_mg_l=250.0,
            chemistry={"dose_al_mg_l": 40.0}
        )

        # Should still return valid results
        assert 0.2 <= result['removal_efficiency'] <= 0.95
        assert result['enhancement_source'] == 'dose_response'
        assert result['ionic_strength_mol_l'] is not None

    def test_low_hrt(self):
        """Low HRT (0.5 hours) with chemistry."""
        result = tss_removal_bsm2(
            HRT_hours=0.5,
            influent_TSS_mg_l=250.0,
            chemistry={"dose_al_mg_l": 10.0}
        )

        # Should still return valid results
        assert 0.2 <= result['removal_efficiency'] <= 0.95
        assert result['baseline_removal'] is not None

    def test_high_temperature(self):
        """High temperature (40°C) with chemistry."""
        result = tss_removal_bsm2(
            HRT_hours=2.0,
            influent_TSS_mg_l=250.0,
            temperature_c=40.0,
            chemistry={"dose_al_mg_l": 10.0}
        )

        # Should return valid results
        assert 0.2 <= result['removal_efficiency'] <= 0.95

        # Higher temperature should improve settling (Arrhenius correction)
        result_20c = tss_removal_bsm2(
            HRT_hours=2.0,
            influent_TSS_mg_l=250.0,
            temperature_c=20.0,
            chemistry={"dose_al_mg_l": 10.0}
        )

        assert result['baseline_removal'] >= result_20c['baseline_removal']

    def test_low_temperature(self):
        """Low temperature (5°C) with chemistry."""
        result = tss_removal_bsm2(
            HRT_hours=2.0,
            influent_TSS_mg_l=250.0,
            temperature_c=5.0,
            chemistry={"dose_al_mg_l": 10.0}
        )

        # Should return valid results
        assert 0.2 <= result['removal_efficiency'] <= 0.95

    def test_high_influent_tss(self):
        """High influent TSS (800 mg/L) industrial wastewater."""
        result = tss_removal_bsm2(
            HRT_hours=2.5,
            influent_TSS_mg_l=800.0,
            chemistry={"dose_fe_mg_l": 15.0, "parameter_set": "industrial_high_tss"}
        )

        # Should handle high TSS
        assert result['removal_efficiency'] is not None
        assert result['baseline_removal'] is not None

    def test_low_influent_tss(self):
        """Low influent TSS (100 mg/L) weak wastewater."""
        result = tss_removal_bsm2(
            HRT_hours=2.0,
            influent_TSS_mg_l=100.0,
            chemistry={"dose_al_mg_l": 10.0}
        )

        # Should handle low TSS
        assert result['removal_efficiency'] is not None
        assert result['baseline_removal'] is not None


class TestCombinedStressConditions:
    """Parameterized combined stress tests as recommended by Codex."""

    @pytest.mark.parametrize("hrt,tss,temp,dose_al,dose_fe", [
        # Low HRT + High TSS + Low Temp
        (0.5, 800.0, 5.0, 20.0, 0.0),
        # High HRT + Low TSS + High Temp
        (3.0, 100.0, 40.0, 10.0, 0.0),
        # Normal conditions with mixed dosing
        (2.0, 300.0, 20.0, 10.0, 15.0),
        # Extreme low conditions
        (0.5, 100.0, 5.0, 5.0, 0.0),
        # Extreme high conditions
        (3.0, 1000.0, 35.0, 30.0, 20.0),
    ])
    def test_combined_stress_conditions(self, hrt, tss, temp, dose_al, dose_fe):
        """Test combined stress conditions with various parameter combinations."""
        result = tss_removal_bsm2(
            HRT_hours=hrt,
            influent_TSS_mg_l=tss,
            temperature_c=temp,
            chemistry={"dose_al_mg_l": dose_al, "dose_fe_mg_l": dose_fe}
        )

        # Should always return valid results
        assert result['removal_efficiency'] is not None
        assert 0.2 <= result['removal_efficiency'] <= 0.95

        # Should always have baseline
        assert result['baseline_removal'] is not None
        assert 0.2 <= result['baseline_removal'] <= 0.95

        # Chemistry should activate with non-zero doses
        if dose_al > 0.05 or dose_fe > 0.05:
            assert result['enhancement_source'] == 'dose_response'
            assert result['chemically_enhanced_removal'] is not None
        else:
            assert result['enhancement_source'] == 'none'
            assert result['chemically_enhanced_removal'] is None

        # Final removal should never be less than baseline
        assert result['removal_efficiency'] >= result['baseline_removal']

    def test_helper_function_consistency(self):
        """Test that helper function returns same value as dict extraction."""
        from utils.removal_efficiency import get_tss_removal_fraction

        # Test with chemistry
        chemistry = {"dose_al_mg_l": 10.0}

        # Get result from main function
        result_dict = tss_removal_bsm2(
            HRT_hours=2.0,
            influent_TSS_mg_l=250.0,
            chemistry=chemistry
        )

        # Get result from helper function
        result_scalar = get_tss_removal_fraction(
            HRT_hours=2.0,
            influent_TSS_mg_l=250.0,
            chemistry=chemistry
        )

        # Should be identical
        assert result_scalar == result_dict['removal_efficiency']

    def test_dose_threshold_behavior(self):
        """Test that small doses below threshold don't activate enhancement."""
        # Test doses below threshold (0.05 mg/L)
        result_below = tss_removal_bsm2(
            HRT_hours=2.0,
            influent_TSS_mg_l=250.0,
            chemistry={"dose_al_mg_l": 0.04}  # Below threshold
        )

        # Should not activate enhancement
        assert result_below['enhancement_source'] == 'none'
        assert result_below['chemically_enhanced_removal'] is None

        # Test dose at threshold
        result_at = tss_removal_bsm2(
            HRT_hours=2.0,
            influent_TSS_mg_l=250.0,
            chemistry={"dose_al_mg_l": 0.05}  # At threshold
        )

        # Should not activate (needs to be > threshold)
        assert result_at['enhancement_source'] == 'none'

        # Test dose above threshold
        result_above = tss_removal_bsm2(
            HRT_hours=2.0,
            influent_TSS_mg_l=250.0,
            chemistry={"dose_al_mg_l": 0.06}  # Above threshold
        )

        # Should activate enhancement
        assert result_above['enhancement_source'] == 'dose_response'
        assert result_above['chemically_enhanced_removal'] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
