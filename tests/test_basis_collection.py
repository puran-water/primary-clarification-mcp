"""
Tests for Basis of Design Collection

Validates parameter collection, validation logic, and state preparation
for ASM2d + MCAS integration.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from basis_collection import (
    ClarifierBasisOfDesign,
    collect_clarifier_basis
)


class TestBasisDataclass:
    """Test ClarifierBasisOfDesign dataclass functionality."""

    def test_minimal_initialization(self):
        """Should initialize with minimum required parameters."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0
        )

        assert basis.flow_m3_d == 1000.0
        assert basis.influent_tss_mg_l == 200.0
        assert basis.temperature_c == 20.0  # Default
        assert basis.influent_ph == 7.2  # Default

    def test_vss_calculation_from_ratio(self):
        """Should calculate VSS from TSS if not provided."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            vss_tss_ratio=0.75
        )

        assert basis.influent_vss_mg_l == 150.0  # 200 * 0.75

    def test_vss_provided_explicitly(self):
        """Should use provided VSS value."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            influent_vss_mg_l=160.0
        )

        assert basis.influent_vss_mg_l == 160.0

    def test_to_dict(self):
        """Should convert to dictionary."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0
        )

        data = basis.to_dict()

        assert isinstance(data, dict)
        assert data["flow_m3_d"] == 1000.0
        assert data["influent_tss_mg_l"] == 200.0

    def test_to_json_string(self):
        """Should serialize to JSON string."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0
        )

        json_str = basis.to_json()

        assert '"flow_m3_d": 1000.0' in json_str
        assert '"influent_tss_mg_l": 200.0' in json_str

    def test_from_dict(self):
        """Should reconstruct from dictionary."""
        data = {
            "flow_m3_d": 1000.0,
            "influent_tss_mg_l": 200.0,
            "peak_factor": 2.5,
            "temperature_c": 20.0,
            "influent_ph": 7.2,
            "vss_tss_ratio": 0.80
        }

        basis = ClarifierBasisOfDesign.from_dict(data)

        assert basis.flow_m3_d == 1000.0
        assert basis.influent_tss_mg_l == 200.0


class TestParameterValidation:
    """Test parameter validation logic."""

    def test_negative_flow_fails(self):
        """Should fail validation for negative flow."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=-1000.0,
            influent_tss_mg_l=200.0
        )

        assert not basis.validation_passed
        assert any("Flow must be positive" in w for w in basis.validation_warnings)

    def test_vss_exceeds_tss_fails(self):
        """Should fail if VSS > TSS."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            influent_vss_mg_l=250.0
        )

        assert not basis.validation_passed
        assert any("VSS cannot exceed TSS" in w for w in basis.validation_warnings)

    def test_extreme_ph_warning(self):
        """Should warn for pH outside typical range."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            influent_ph=11.0
        )

        assert any("pH" in w and "outside typical range" in w for w in basis.validation_warnings)

    def test_extreme_temperature_warning(self):
        """Should warn for temperature outside typical range."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            temperature_c=50.0
        )

        assert any("Temperature" in w and "outside typical range" in w for w in basis.validation_warnings)

    def test_vss_tss_ratio_warning(self):
        """Should warn if VSS/TSS ratio is atypical."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            influent_vss_mg_l=20.0  # 0.10 ratio
        )

        assert any("VSS/TSS ratio" in w and "outside typical range" in w for w in basis.validation_warnings)

    def test_removal_efficiency_warning(self):
        """Should warn for unrealistic removal efficiency."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            target_tss_removal_pct=95.0
        )

        assert any("TSS removal" in w and "outside typical range" in w for w in basis.validation_warnings)

    def test_underflow_solids_warning(self):
        """Should warn for unrealistic underflow concentration."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            target_underflow_solids_pct=15.0
        )

        assert any("underflow solids" in w and "outside typical range" in w for w in basis.validation_warnings)


class TestTDSValidation:
    """Test TDS vs sum of ions validation."""

    def test_tds_matches_ion_sum(self):
        """Should pass if TDS matches sum of ions."""
        ions = {
            "Ca_mg_l": 80.0,
            "Mg_mg_l": 20.0,
            "Na_mg_l": 150.0,
            "K_mg_l": 10.0,
            "Cl_mg_l": 200.0,
            "SO4_mg_l": 50.0
        }
        ion_sum = sum(ions.values())  # 510 mg/L

        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            tds_mg_l=510.0,
            ion_composition=ions
        )

        # Should not warn about TDS mismatch
        assert not any("differs from TDS" in w for w in basis.validation_warnings)

    def test_tds_ion_mismatch_warning(self):
        """Should warn if TDS differs significantly from ion sum (with ≥80% ion coverage)."""
        ions = {
            "Ca_mg_l": 80.0,
            "Mg_mg_l": 20.0,
            "Na_mg_l": 150.0,
            "K_mg_l": 10.0,
            "Cl_mg_l": 200.0,
            "SO4_mg_l": 50.0,
            "HCO3_mg_l": 250.0,  # Added to reach ≥80% coverage (7/8 = 87.5%)
        }
        ion_sum = sum(ions.values())  # 760 mg/L

        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            tds_mg_l=1200.0,  # 58% difference - well above 20% threshold
            ion_composition=ions
        )

        # Should warn about TDS mismatch (>20% threshold with ≥80% coverage)
        assert any("differs from TDS" in w for w in basis.validation_warnings)


class TestChargeBalance:
    """Test charge balance validation."""

    def test_balanced_ions_pass(self):
        """Should pass for electroneutral ion composition."""
        # Ca: 80 mg/L / 40.08 * 2 * 1000 = 3.99 meq/L
        # Mg: 20 mg/L / 24.31 * 2 * 1000 = 1.64 meq/L
        # Na: 150 mg/L / 22.99 * 1 * 1000 = 6.53 meq/L
        # Total cations ≈ 12.16 meq/L

        # Cl: 210 mg/L / 35.45 * 1 * 1000 = 5.92 meq/L
        # SO4: 100 mg/L / 96.06 * 2 * 1000 = 2.08 meq/L
        # HCO3: 250 mg/L / 61.02 * 1 * 1000 = 4.10 meq/L
        # Total anions ≈ 12.10 meq/L
        # Imbalance ≈ 0.5%

        ions = {
            "Ca_mg_l": 80.0,
            "Mg_mg_l": 20.0,
            "Na_mg_l": 150.0,
            "Cl_mg_l": 210.0,
            "SO4_mg_l": 100.0,
            "HCO3_mg_l": 250.0
        }

        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            ion_composition=ions
        )

        # Should not warn about charge imbalance
        assert not any("Charge imbalance" in w for w in basis.validation_warnings)

    def test_imbalanced_ions_warning(self):
        """Should warn for significant charge imbalance."""
        # Heavily imbalanced: lots of cations, few anions
        ions = {
            "Ca_mg_l": 200.0,
            "Mg_mg_l": 50.0,
            "Na_mg_l": 300.0,
            "Cl_mg_l": 50.0,  # Very low
            "SO4_mg_l": 20.0   # Very low
        }

        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            ion_composition=ions
        )

        # Should warn about charge imbalance (>5% threshold)
        assert any("Charge imbalance" in w for w in basis.validation_warnings)


class TestTotalNitrogenValidation:
    """Test total nitrogen consistency checks."""

    def test_tn_less_than_tkn_fails(self):
        """Should fail if TN < TKN."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            influent_tkn_mg_l=50.0,
            total_nitrogen_mg_n_l=40.0  # Less than TKN
        )

        assert any("Total nitrogen" in w and "cannot be less than TKN" in w
                   for w in basis.validation_warnings)

    def test_tn_greater_than_tkn_passes(self):
        """Should pass if TN >= TKN."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            influent_tkn_mg_l=50.0,
            total_nitrogen_mg_n_l=60.0  # Greater than TKN (includes NO3)
        )

        # Should not warn about TN/TKN mismatch
        assert not any("cannot be less than TKN" in w for w in basis.validation_warnings)


class TestCollectFunction:
    """Test collect_clarifier_basis() function."""

    def test_successful_collection(self):
        """Should successfully collect and validate basis."""
        result = collect_clarifier_basis(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            influent_cod_mg_l=400.0,
            influent_tkn_mg_l=50.0,
            influent_tp_mg_l=8.0
        )

        assert result["status"] == "success"
        assert "basis" in result
        assert result["basis"]["flow_m3_d"] == 1000.0

    def test_warning_status_for_invalid_params(self):
        """Should return warning status for hard validation failures."""
        result = collect_clarifier_basis(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            influent_vss_mg_l=250.0  # VSS > TSS - hard failure
        )

        assert result["status"] == "warning"
        assert len(result["warnings"]) > 0
        assert not result["basis"]["validation_passed"]

    def test_next_steps_for_incomplete_data(self):
        """Should suggest next steps for incomplete data."""
        result = collect_clarifier_basis(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0
            # Missing COD, BOD, TKN, TP
        )

        assert "next_steps" in result
        assert any("COD or BOD5" in step for step in result["next_steps"])
        assert any("TKN" in step for step in result["next_steps"])
        assert any("TP" in step for step in result["next_steps"])

    def test_ion_estimation_recommendation(self):
        """Should recommend ion estimation if TDS provided but no ions."""
        result = collect_clarifier_basis(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            tds_mg_l=500.0,
            estimate_ions_from_tds=True
        )

        assert any("estimate ion composition from TDS" in step
                   for step in result["next_steps"])

    def test_complete_data_next_steps(self):
        """Should recommend Phase 3 if data is complete."""
        ions = {
            "Ca_mg_l": 80.0,
            "Mg_mg_l": 20.0,
            "Na_mg_l": 150.0,
            "K_mg_l": 10.0,
            "Cl_mg_l": 210.0,
            "SO4_mg_l": 100.0,
            "HCO3_mg_l": 250.0
        }

        result = collect_clarifier_basis(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            influent_cod_mg_l=400.0,
            influent_tkn_mg_l=50.0,
            influent_tp_mg_l=8.0,
            ion_composition=ions
        )

        assert any("Ready for Phase 3" in step for step in result["next_steps"])

    def test_error_handling(self):
        """Should handle errors gracefully."""
        # Pass invalid type to trigger exception
        result = collect_clarifier_basis(
            flow_m3_d="invalid",  # Should be float
            influent_tss_mg_l=200.0
        )

        assert result["status"] == "error"
        assert "error" in result


class TestWastewaterTypes:
    """Test wastewater type handling."""

    def test_municipal_default(self):
        """Should default to municipal wastewater."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0
        )

        assert basis.wastewater_type == "municipal"

    def test_industrial_types(self):
        """Should accept various industrial wastewater types."""
        for ww_type in ["dairy", "brewery", "pharmaceutical", "industrial"]:
            basis = ClarifierBasisOfDesign(
                flow_m3_d=1000.0,
                influent_tss_mg_l=200.0,
                wastewater_type=ww_type
            )

            assert basis.wastewater_type == ww_type


class TestChemicalDosing:
    """Test chemical dosing parameter handling."""

    def test_no_chemicals_default(self):
        """Should default to no chemical dosing."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0
        )

        assert basis.coagulant_type is None
        assert basis.coagulant_dose_mg_l == 0.0
        assert basis.polymer_type is None
        assert basis.polymer_dose_mg_l == 0.0

    def test_coagulant_dosing(self):
        """Should store coagulant dosing information."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            coagulant_type="alum",
            coagulant_dose_mg_l=50.0
        )

        assert basis.coagulant_type == "alum"
        assert basis.coagulant_dose_mg_l == 50.0

    def test_polymer_dosing(self):
        """Should store polymer dosing information."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            polymer_type="anionic",
            polymer_dose_mg_l=2.0
        )

        assert basis.polymer_type == "anionic"
        assert basis.polymer_dose_mg_l == 2.0

    def test_alkalinity_consumption(self):
        """Should store alkalinity consumption data."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            coagulant_type="ferric_chloride",
            coagulant_dose_mg_l=100.0,
            alkalinity_consumed_mg_caco3_l=150.0
        )

        assert basis.alkalinity_consumed_mg_caco3_l == 150.0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_flow(self):
        """Should fail for zero flow."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=0.0,
            influent_tss_mg_l=200.0
        )

        assert not basis.validation_passed
        assert any("Flow must be positive" in w for w in basis.validation_warnings)

    def test_near_zero_concentrations(self):
        """Should handle near-zero concentrations gracefully."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=0.1,  # Very low
            influent_vss_mg_l=0.05
        )

        # Should not fail, just warn about low VSS/TSS ratio
        assert basis.flow_m3_d == 1000.0

    def test_extreme_alkalinity_temperature(self):
        """Should handle high alkalinity and temperature combination."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            temperature_c=35.0,
            alkalinity_mg_caco3_l=500.0  # Very high
        )

        # Should accept but may warn about temperature
        assert basis.alkalinity_mg_caco3_l == 500.0

    def test_negative_concentrations_prevented(self):
        """Should prevent negative concentrations via validation."""
        # Note: dataclass doesn't prevent negative values, but validation warns
        basis = ClarifierBasisOfDesign(
            flow_m3_d=-100.0,  # Negative
            influent_tss_mg_l=200.0
        )

        assert not basis.validation_passed


class TestJSONSerialization:
    """Test JSON file I/O operations."""

    def test_json_file_write_read(self, tmp_path):
        """Should write and read JSON file correctly."""
        import os

        # Create basis
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            influent_cod_mg_l=400.0,
            temperature_c=22.0
        )

        # Write to file
        filepath = tmp_path / "test_basis.json"
        basis.to_json(str(filepath))

        # Verify file exists
        assert filepath.exists()

        # Read back from file
        with open(filepath, 'r') as f:
            json_str = f.read()

        basis_loaded = ClarifierBasisOfDesign.from_json(json_str)

        # Verify data matches
        assert basis_loaded.flow_m3_d == 1000.0
        assert basis_loaded.influent_tss_mg_l == 200.0
        assert basis_loaded.influent_cod_mg_l == 400.0
        assert basis_loaded.temperature_c == 22.0

    def test_json_round_trip_with_warnings(self):
        """Should preserve validation warnings in round-trip."""
        # Create basis with warnings
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            influent_ph=11.5  # Extreme pH - triggers warning
        )

        # Should have warnings
        assert len(basis.validation_warnings) > 0

        # Round-trip
        json_str = basis.to_json()
        basis_loaded = ClarifierBasisOfDesign.from_json(json_str)

        # Warnings are recalculated in __post_init__, so should be present
        assert len(basis_loaded.validation_warnings) > 0


class TestIonEstimationModes:
    """Test ion estimation behavior."""

    def test_estimate_disabled_no_ions_warning(self):
        """Should warn when estimation disabled and no ions provided."""
        result = collect_clarifier_basis(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            influent_cod_mg_l=400.0,
            influent_tkn_mg_l=50.0,
            influent_tp_mg_l=8.0,
            estimate_ions_from_tds=False  # Disabled
            # No ion_composition provided
        )

        # Should recommend providing ions
        assert any("CRITICAL" in step and "Ion composition required" in step
                   for step in result["next_steps"])

    def test_estimate_enabled_with_tds(self):
        """Should recommend estimation when TDS provided."""
        result = collect_clarifier_basis(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            tds_mg_l=500.0,
            estimate_ions_from_tds=True
        )

        # Should indicate estimation will be used
        assert any("estimate ion composition from TDS" in step
                   for step in result["next_steps"])

    def test_estimate_enabled_without_tds(self):
        """Should warn when estimation enabled but no TDS."""
        result = collect_clarifier_basis(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            estimate_ions_from_tds=True
            # No TDS provided
        )

        # Should warn about missing TDS
        assert any("TDS" in step for step in result["next_steps"])


class TestPartialIonCoverage:
    """Test TDS validation with partial ion coverage."""

    def test_partial_ions_no_tds_warning(self):
        """Should not warn about TDS mismatch when <80% ions provided."""
        ions = {
            "Ca_mg_l": 80.0,
            "Mg_mg_l": 20.0,
            "Na_mg_l": 150.0,
            # Only 3 out of 8 major ions = 37.5% coverage
        }

        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            tds_mg_l=500.0,
            ion_composition=ions
        )

        # Should NOT warn about TDS mismatch due to low coverage
        assert not any("differs from TDS" in w for w in basis.validation_warnings)

    def test_full_ions_validates_tds(self):
        """Should validate TDS when all major ions provided."""
        ions = {
            "Ca_mg_l": 80.0,
            "Mg_mg_l": 20.0,
            "Na_mg_l": 150.0,
            "K_mg_l": 10.0,
            "Cl_mg_l": 200.0,
            "SO4_mg_l": 50.0,
            "HCO3_mg_l": 250.0,
            "CO3_mg_l": 10.0
        }
        ion_sum = sum(ions.values())  # 770 mg/L

        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            tds_mg_l=800.0,  # Only 3.9% difference - within tolerance
            ion_composition=ions
        )

        # Should NOT warn (within 20% threshold)
        assert not any("differs from TDS" in w for w in basis.validation_warnings)


class TestNitrogenSpeciation:
    """Test nitrogen speciation parameters."""

    def test_nitrogen_speciation_stored(self):
        """Should store nitrogen speciation when provided."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            influent_nh4_n_mg_l=25.0,
            influent_no3_n_mg_l=5.0,
            influent_no2_n_mg_l=0.5,
            total_nitrogen_mg_n_l=50.0
        )

        assert basis.influent_nh4_n_mg_l == 25.0
        assert basis.influent_no3_n_mg_l == 5.0
        assert basis.influent_no2_n_mg_l == 0.5
        assert basis.total_nitrogen_mg_n_l == 50.0

    def test_new_water_quality_parameters(self):
        """Should store new water quality parameters."""
        basis = ClarifierBasisOfDesign(
            flow_m3_d=1000.0,
            influent_tss_mg_l=200.0,
            influent_do_mg_l=2.0,
            influent_orp_mv=-150.0,
            specific_conductivity_us_cm=1200.0,
            influent_toc_mg_l=150.0,
            influent_doc_mg_l=80.0,
            influent_silica_mg_l=15.0
        )

        assert basis.influent_do_mg_l == 2.0
        assert basis.influent_orp_mv == -150.0
        assert basis.specific_conductivity_us_cm == 1200.0
        assert basis.influent_toc_mg_l == 150.0
        assert basis.influent_doc_mg_l == 80.0
        assert basis.influent_silica_mg_l == 15.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
