"""Check if volume is conserved in birth distribution."""

import numpy as np
from utils.population_balance import PopulationBalanceModel

diameters = np.logspace(-6, -4, 5)
zeta_potentials = np.full(5, -20.0)

pbm = PopulationBalanceModel(
    diameter_bins=diameters,
    zeta_potentials_mV=zeta_potentials,
    ionic_strength_M=0.01,
    temperature_c=20.0,
    velocity_gradient=50.0
)

print("Testing volume conservation in pivot method:")
print()

# Test a few collisions
for i in [0, 1, 2]:
    for j in [i, i+1]:
        if j >= pbm.n_bins:
            continue

        v_i = diameters[i]**3
        v_j = diameters[j]**3
        v_combined = v_i + v_j

        k_lower, k_upper, eta = pbm._find_pivot_bins(v_combined)

        # Volume distributed to bins
        v_lower = diameters[k_lower]**3
        v_upper = diameters[k_upper]**3

        v_distributed = (1.0 - eta) * v_lower + eta * v_upper

        error = abs(v_distributed - v_combined) / v_combined * 100

        print(f"Collision ({i},{j}):")
        print(f"  v_combined = {v_combined:.3e}")
        print(f"  Maps to bins ({k_lower},{k_upper}) with eta={eta:.4f}")
        print(f"  v_distributed = (1-eta)*v_{k_lower} + eta*v_{k_upper}")
        print(f"                = {(1-eta):.4f}*{v_lower:.3e} + {eta:.4f}*{v_upper:.3e}")
        print(f"                = {v_distributed:.3e}")
        print(f"  Error: {error:.2f}%")
        print()
