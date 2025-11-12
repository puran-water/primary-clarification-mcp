"""
Process simulation for primary clarifier.

Stage 3 of the normalized workflow.
Uses JobManager for background execution following anaerobic/aerobic pattern.
"""

from typing import Dict, Any
from core.state import clarifier_design_state


async def simulate_clarifier_system(
    use_current_state: bool = True,
    simulation_mode: str = "empirical",
    include_costing: bool = True
) -> Dict[str, Any]:
    """
    Run clarifier simulation via JobManager.

    TODO: Implement in Week 4
    - Create utils/simulate_cli.py (CLI wrapper with RO artifact pattern)
    - Implement empirical removal efficiency correlations
    - Implement settling flux calculations
    - Integrate static costing (Phase 1)
    - Launch via JobManager from mcp_common
    - Return job_id for status tracking

    Args:
        use_current_state: Use sizing from clarifier_design_state
        simulation_mode: "empirical" (Phase 1) or "qsdsan" (Phase 2)
        include_costing: Include economic analysis

    Returns:
        Job ID for background execution
    """
    return {
        "status": "not_implemented",
        "message": "Process simulation to be implemented in Week 4",
        "next_steps": [
            "Week 4: Create utils/simulate_cli.py with RO artifact pattern",
            "Week 4: Implement empirical correlations in utils/removal_efficiency.py",
            "Week 4: Create data/removal_correlations.json",
            "Week 4: Create data/equipment_costs.json (static curves)",
            "Week 4: Integrate JobManager from mcp_common",
            "Week 5 (Phase 1.5): Add WaterTAP costing via utils/costing_cli.py"
        ]
    }
