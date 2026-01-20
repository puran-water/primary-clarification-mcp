"""Debug time integration to see where mass is lost."""

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

N0 = np.array([1e12, 5e11, 1e11, 5e10, 1e10])

# Initial M3
M3_initial = np.sum(N0 * diameters**3)
print(f"M3 initial: {M3_initial:.6e}")
print()

# Solve for short time with dense output
result = pbm.solve(N0, t_span=(0, 60.0), rtol=1e-6, atol=1e-8)

print(f"Integration success: {result['success']}")
print(f"Number of time steps: {len(result['t'])}")
print()

# Check M3 at each time step
print("M3 evolution:")
for i, t in enumerate(result['t']):
    N = result['N'][:, i]
    M3 = np.sum(N * diameters**3)
    error = abs(M3 - M3_initial) / M3_initial * 100
    print(f"t={t:6.2f}s: M3={M3:.6e}, error={error:6.2f}%")

# Final check
N_final = result['N'][:, -1]
M3_final = np.sum(N_final * diameters**3)
print()
print(f"M3 final: {M3_final:.6e}")
print(f"M3 conservation error: {abs(M3_final - M3_initial) / M3_initial * 100:.2f}%")
