"""Debug PBM fixed-pivot implementation."""

import numpy as np
from utils.population_balance import PopulationBalanceModel

# Simple 5-bin test
diameters = np.logspace(-6, -4, 5)
zeta_potentials = np.full(5, -20.0)

pbm = PopulationBalanceModel(
    diameter_bins=diameters,
    zeta_potentials_mV=zeta_potentials,
    ionic_strength_M=0.01,
    temperature_c=20.0,
    velocity_gradient=50.0
)

N = np.array([1e12, 5e11, 1e11, 5e10, 1e10])

print("Diameter bins (um):", diameters * 1e6)
print("Initial N:", N)
print()

# Test fixed-pivot for a few collisions
print("Testing pivot mapping:")
for i in range(3):
    for j in range(i, 3):
        v_i = diameters[i]**3
        v_j = diameters[j]**3
        v_combined = v_i + v_j

        k_lower, k_upper, eta = pbm._find_pivot_bins(v_combined)

        d_combined = v_combined**(1/3) * 1e6  # um
        print(f"  ({i},{j}): d_i={diameters[i]*1e6:.2f} + d_j={diameters[j]*1e6:.2f} = {d_combined:.2f} um")
        print(f"           -> bins ({k_lower}, {k_upper}), eta={eta:.3f}")

print()
print("Aggregation rate:")
dN_dt = pbm.aggregation_rate(N)
print("dN/dt:", dN_dt)
print()

# Check M3 conservation
M3_before = np.sum(N * diameters**3)
M3_rate = np.sum(dN_dt * diameters**3)

print(f"M3 before: {M3_before:.3e}")
print(f"d(M3)/dt: {M3_rate:.3e}")
print(f"Relative M3 rate: {abs(M3_rate/M3_before):.1%}")
