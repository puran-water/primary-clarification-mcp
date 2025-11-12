"""State management for primary clarifier design."""

from typing import Dict, Any, Optional


class ClarifierDesignState:
    """
    Manages state across tools for primary clarifier design.

    State is organized into stages following the normalized workflow:
    1. Basis of Design - Input parameters
    2. Heuristic Config - Sizing results
    3. Simulation Results - Process modeling outputs
    4. Economics - CAPEX, OPEX, LCOW

    """

    def __init__(self):
        # Stage 1: Basis of Design
        self.basis_of_design = {
            "hydraulic": {},      # flow_rate, peak_factor, temperature
            "influent": {},       # tss, vss, cod, bod5, tkn, tp, oil_grease, ph
            "targets": {},        # tss_removal_pct, underflow_solids_pct
            "chemical_dosing": {} # coagulant_type, polymer_type
        }

        # Stage 2: Heuristic Sizing Results
        self.heuristic_config = {
            "geometry": {},       # diameter, area, depth, volume
            "performance": {},    # sor, slr, hrt, weir_loading
            "power": {},          # flash_mix, flocculation, scraper
            "chemicals": {}       # coagulant_dose, polymer_dose
        }

        # Stage 3: Simulation Results
        self.simulation_results = {
            "settling": {},              # settling_velocity, flux_curve
            "removal_efficiency": {},    # tss, vss, cod, bod5, tp removal
            "effluent_quality": {},      # effluent concentrations
            "sludge_production": {}      # underflow_flow, underflow_concentration
        }

        # Stage 4: Economics
        self.economics = {
            "capex": {},          # equipment, installation, indirect, total
            "opex_annual": {},    # electricity, chemicals, labor, maintenance
            "lcow_usd_m3": None   # Levelized cost of water
        }

        # Optional: Calculation traces for transparency
        self.calculation_traces = {}

        # Last simulation metadata (for caching)
        self.last_simulation = None

    def reset(self, scope: str = "all"):
        """
        Reset state with optional scoping.

        Args:
            scope: "all" (full reset), "simulation" (keep basis and sizing),
                   or "costing" (keep everything except economics)
        """
        if scope == "all":
            self.__init__()
        elif scope == "simulation":
            self.simulation_results = {
                "settling": {},
                "removal_efficiency": {},
                "effluent_quality": {},
                "sludge_production": {}
            }
            self.economics = {
                "capex": {},
                "opex_annual": {},
                "lcow_usd_m3": None
            }
            self.last_simulation = None
        elif scope == "costing":
            self.economics = {
                "capex": {},
                "opex_annual": {},
                "lcow_usd_m3": None
            }
        else:
            raise ValueError(f"Invalid reset scope: {scope}. Must be 'all', 'simulation', or 'costing'")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert state to dictionary for serialization.

        Returns:
            Dictionary representation of complete design state
        """
        result = {
            "basis_of_design": self.basis_of_design,
            "heuristic_config": self.heuristic_config,
            "simulation_results": self.simulation_results,
            "economics": self.economics
        }

        # Add calculation traces if populated
        if self.calculation_traces:
            result["calculation_traces"] = self.calculation_traces

        # Add lightweight simulation summary if available
        if self.last_simulation:
            result["last_simulation_summary"] = {
                "timestamp": str(self.last_simulation.get("timestamp", "N/A")),
                "status": self.last_simulation.get("status", "N/A"),
                "mode": self.last_simulation.get("mode", "N/A")
            }

        return result

    def from_dict(self, data: Dict[str, Any]):
        """
        Load state from dictionary.

        Args:
            data: Dictionary representation of design state
        """
        self.basis_of_design = data.get("basis_of_design", {})
        self.heuristic_config = data.get("heuristic_config", {})
        self.simulation_results = data.get("simulation_results", {})
        self.economics = data.get("economics", {})
        self.calculation_traces = data.get("calculation_traces", {})
        # Don't load last_simulation - it's runtime metadata

    def get_completion_status(self) -> Dict[str, bool]:
        """
        Check which workflow stages are completed.

        Returns:
            Dictionary with boolean flags for each stage
        """
        return {
            "basis_collected": bool(self.basis_of_design.get("hydraulic")),
            "sizing_complete": bool(self.heuristic_config.get("geometry")),
            "simulation_complete": bool(self.simulation_results.get("removal_efficiency")),
            "costing_complete": bool(self.economics.get("capex"))
        }

    def get_next_steps(self) -> list:
        """
        Determine next recommended actions based on current state.

        Returns:
            List of recommended next steps
        """
        status = self.get_completion_status()
        steps = []

        if not status["basis_collected"]:
            steps.append("Call collect_clarifier_basis() to define design parameters")
        elif not status["sizing_complete"]:
            steps.append("Call size_clarifier_heuristic() to perform preliminary sizing")
        elif not status["simulation_complete"]:
            steps.append("Call simulate_clarifier_system() to run process simulation")
        elif not status["costing_complete"]:
            steps.append("Costing included in simulation - check economics in state")
        else:
            steps.append("Design complete! Use export_design_state() to save results")
            steps.append("Or call summarize_clarifier_effluent() for downstream integration")

        return steps


# Global state instance (singleton)
clarifier_design_state = ClarifierDesignState()
