"""
State management tools for primary clarifier design.

Provides export/import, reset, and summary generation capabilities.
"""

import json
from typing import Optional, Dict, Any
from pathlib import Path
from core.state import clarifier_design_state


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


async def summarize_clarifier_effluent() -> Dict[str, Any]:
    """
    Generate effluent summary for downstream MCP consumption.

    Returns:
        Effluent characteristics with min/max removal envelopes
    """
    # Check if simulation results are available
    if not clarifier_design_state.simulation_results.get("removal_efficiency"):
        return {
            "status": "error",
            "message": "No simulation results available. Run simulate_clarifier_system() first."
        }

    # TODO: Implement in Week 4-5
    # - Extract effluent concentrations
    # - Calculate min/max envelopes considering uncertainties
    # - Format for downstream aerobic/anaerobic MCP consumption
    # - Include sludge production data

    return {
        "status": "not_implemented",
        "message": "Effluent summary generation to be implemented in Week 4-5",
        "next_steps": [
            "Week 4: Implement effluent extraction from simulation results",
            "Week 4: Calculate removal efficiency envelopes",
            "Week 5: Add sludge production summary",
            "Week 5: Format for downstream MCP integration"
        ]
    }
