"""
State management tools for primary clarifier design.

Provides export/import, reset, and summary generation capabilities.
"""

import json
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime
from core.state import clarifier_design_state

# Import plant_state for multi-stream interchange
try:
    from plant_state.interchange import StreamState, UnitOutputState, StateConverter
    from plant_state.mass_balance import MassBalanceValidator
    PLANT_STATE_AVAILABLE = True
except ImportError:
    PLANT_STATE_AVAILABLE = False


async def get_design_state() -> Dict[str, Any]:
    """
    Get current clarifier design state.

    Returns:
        Complete design state with completion status and next steps
    """
    state_dict = clarifier_design_state.to_dict()
    completion_status = clarifier_design_state.get_completion_status()
    next_steps = clarifier_design_state.get_next_steps()

    return {
        "status": "success",
        "design_state": state_dict,
        "completion_status": completion_status,
        "next_steps": next_steps
    }


async def reset_design(scope: str = "all") -> Dict[str, Any]:
    """
    Reset design state with optional scoping.

    Args:
        scope: "all", "simulation", or "costing"

    Returns:
        Reset confirmation
    """
    try:
        clarifier_design_state.reset(scope)
        return {
            "status": "success",
            "message": f"Design state reset (scope: {scope})",
            "scope": scope
        }
    except ValueError as e:
        return {
            "status": "error",
            "message": str(e)
        }


async def export_design_state(filepath: Optional[str] = None) -> Dict[str, Any]:
    """
    Export current design state to JSON file.

    Args:
        filepath: Output file path (default: ./clarifier_design_state.json)

    Returns:
        Export status and filepath
    """
    if filepath is None:
        filepath = "./clarifier_design_state.json"

    try:
        state_dict = clarifier_design_state.to_dict()

        # Ensure directory exists
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w') as f:
            json.dump(state_dict, f, indent=2)

        return {
            "status": "success",
            "message": f"Design state exported successfully",
            "filepath": filepath,
            "size_bytes": Path(filepath).stat().st_size
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to export state: {str(e)}"
        }


async def import_design_state(filepath: str) -> Dict[str, Any]:
    """
    Import design state from JSON file.

    Args:
        filepath: Input file path

    Returns:
        Import status and loaded state summary
    """
    try:
        with open(filepath, 'r') as f:
            state_dict = json.load(f)

        clarifier_design_state.from_dict(state_dict)
        completion_status = clarifier_design_state.get_completion_status()

        return {
            "status": "success",
            "message": f"Design state imported successfully",
            "filepath": filepath,
            "completion_status": completion_status
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "message": f"File not found: {filepath}"
        }
    except json.JSONDecodeError as e:
        return {
            "status": "error",
            "message": f"Invalid JSON file: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to import state: {str(e)}"
        }


async def summarize_clarifier_effluent(
    validate_mass_balance: bool = True,
    target_overflow: str = "AEROBIC",
    target_underflow: str = "THICKENER"
) -> Dict[str, Any]:
    """
    Generate multi-stream effluent summary for downstream MCP consumption.

    Creates UnitOutputState with overflow (to aerobic) + underflow (to thickening/digestion)
    using plant_state stream-first architecture.

    Args:
        validate_mass_balance: Run Pyomo mass balance validation (default: True)
        target_overflow: Target unit for overflow stream (default: "AEROBIC")
        target_underflow: Target unit for underflow stream (default: "THICKENER")

    Returns:
        Dict with UnitOutputState and validation results, or error if plant_state not available
    """
    # Check plant_state availability
    if not PLANT_STATE_AVAILABLE:
        return {
            "status": "error",
            "message": "plant_state module not available. Install with: pip install -e ../plant_state"
        }

    # Check if simulation results are available
    if not clarifier_design_state.simulation_results.get("removal_efficiency"):
        return {
            "status": "error",
            "message": "No simulation results available. Run simulate_clarifier_system() first."
        }

    try:
        # Extract influent data from basis of design
        basis = clarifier_design_state.basis_of_design
        influent_flow = basis["hydraulic"]["flow_m3_d"]
        influent_temp = basis["hydraulic"]["temperature_c"]
        influent_ph = basis["influent_quality"].get("pH", 7.2)

        # Extract influent concentrations
        influent_quality = basis["influent_quality"]
        influent_state = {
            "TSS_mg_l": influent_quality.get("tss_mg_l", 0),
            "VSS_mg_l": influent_quality.get("vss_mg_l", 0),
            "COD_mg_l": influent_quality.get("cod_mg_l", 0),
            "BOD5_mg_l": influent_quality.get("bod5_mg_l", 0),
            "TN_mg_l": influent_quality.get("tkn_mg_l", 0),
            "TP_mg_l": influent_quality.get("tp_mg_l", 0),
        }

        # Extract removal efficiencies
        removal = clarifier_design_state.simulation_results["removal_efficiency"]

        # Calculate overflow (effluent) concentrations
        overflow_state = {
            "TSS_mg_l": influent_state["TSS_mg_l"] * (1 - removal.get("tss_pct", 0) / 100),
            "VSS_mg_l": influent_state["VSS_mg_l"] * (1 - removal.get("vss_pct", 0) / 100),
            "COD_mg_l": influent_state["COD_mg_l"] * (1 - removal.get("cod_pct", 0) / 100),
            "BOD5_mg_l": influent_state["BOD5_mg_l"] * (1 - removal.get("bod5_pct", 0) / 100),
            "TN_mg_l": influent_state["TN_mg_l"],  # TN mostly conservative
            "TP_mg_l": influent_state["TP_mg_l"] * (1 - removal.get("tp_pct", 0) / 100),
        }

        # Extract sludge production data
        sludge = clarifier_design_state.simulation_results.get("sludge_production", {})
        underflow_flow = sludge.get("underflow_flow_m3_d", influent_flow * 0.05)  # Default 5%
        overflow_flow = influent_flow - underflow_flow

        # Calculate underflow concentrations (mass balance)
        underflow_state = {
            "TSS_mg_l": (influent_state["TSS_mg_l"] * influent_flow -
                        overflow_state["TSS_mg_l"] * overflow_flow) / underflow_flow,
            "VSS_mg_l": (influent_state["VSS_mg_l"] * influent_flow -
                        overflow_state["VSS_mg_l"] * overflow_flow) / underflow_flow,
            "COD_mg_l": (influent_state["COD_mg_l"] * influent_flow -
                        overflow_state["COD_mg_l"] * overflow_flow) / underflow_flow,
            "BOD5_mg_l": (influent_state["BOD5_mg_l"] * influent_flow -
                         overflow_state["BOD5_mg_l"] * overflow_flow) / underflow_flow,
            "TN_mg_l": influent_state["TN_mg_l"],  # Conservative
            "TP_mg_l": (influent_state["TP_mg_l"] * influent_flow -
                       overflow_state["TP_mg_l"] * overflow_flow) / underflow_flow,
        }

        # Create StreamState objects
        unit_id = f"PRIMARY_{basis['hydraulic'].get('unit_id', '001')}"

        overflow_stream = StreamState(
            stream_id=f"{unit_id}_OVERFLOW",
            source_unit_id=unit_id,
            target_unit_id=target_overflow,
            stream_type="overflow",
            flow_m3_d=overflow_flow,
            temperature_c=influent_temp,
            pH=influent_ph,
            state_format="composite",
            state_dict=overflow_state,
            metadata={
                "simulation_timestamp": datetime.now().isoformat(),
                "removal_efficiency": removal,
            }
        )

        underflow_stream = StreamState(
            stream_id=f"{unit_id}_UNDERFLOW",
            source_unit_id=unit_id,
            target_unit_id=target_underflow,
            stream_type="underflow",
            flow_m3_d=underflow_flow,
            temperature_c=influent_temp,
            pH=influent_ph,
            state_format="composite",
            state_dict=underflow_state,
            metadata={
                "simulation_timestamp": datetime.now().isoformat(),
                "sludge_concentration_factor": underflow_state["TSS_mg_l"] / influent_state["TSS_mg_l"] if influent_state["TSS_mg_l"] > 0 else 0,
            }
        )

        # Bundle into UnitOutputState
        output = UnitOutputState(
            unit_id=unit_id,
            unit_type="primary_clarifier",
            timestamp=datetime.now().isoformat(),
            streams={"overflow": overflow_stream, "underflow": underflow_stream}
        )

        # Optional mass balance validation
        mass_balance_results = {}
        if validate_mass_balance:
            try:
                validator = MassBalanceValidator()

                # Create influent stream for validation
                influent_stream = StreamState(
                    stream_id=f"{unit_id}_INFLUENT",
                    source_unit_id="UPSTREAM",
                    target_unit_id=unit_id,
                    stream_type="main",
                    flow_m3_d=influent_flow,
                    temperature_c=influent_temp,
                    pH=influent_ph,
                    state_format="composite",
                    state_dict=influent_state
                )

                mass_balance_results = validator.validate_clarifier(
                    influent_stream,
                    {"overflow": overflow_stream, "underflow": underflow_stream}
                )

                output.mass_balance_validated = True
                output.mass_balance_results = mass_balance_results

            except Exception as e:
                mass_balance_results = {
                    "error": f"Mass balance validation failed: {str(e)}",
                    "valid": False
                }

        # Return formatted response
        return {
            "status": "success",
            "unit_output": output.to_dict(),
            "sfiles_notation": output.get_sfiles_notation(),
            "mass_balance": mass_balance_results if validate_mass_balance else None,
            "summary": {
                "total_flow_in": influent_flow,
                "total_flow_out": output.get_total_outflow(),
                "overflow_fraction": overflow_flow / influent_flow,
                "underflow_fraction": underflow_flow / influent_flow,
                "tss_removal_pct": removal.get("tss_pct", 0),
                "cod_removal_pct": removal.get("cod_pct", 0),
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to generate effluent summary: {str(e)}",
            "traceback": str(e.__class__.__name__)
        }
