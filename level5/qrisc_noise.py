# qrisc_noise.py
"""
Q-RISC++ Noise Model
=====================
Simulates real quantum hardware constraints:
  - Depolarizing gate errors  (1Q: ~0.1%, 2Q: ~1%)
  - T1 relaxation (energy decay)
  - T2 dephasing  (coherence loss)
  - Measurement readout errors (~1.5%)

Parameters based on real IBM Eagle/Heron processor specs.
"""

from qiskit_aer.noise import (
    NoiseModel, depolarizing_error,
    thermal_relaxation_error, ReadoutError
)

IBM_EAGLE_PARAMS = {
    'p1q':     0.001,
    'p2q':     0.010,
    't1_us':   100.0,
    't2_us':   120.0,
    't_1q_ns': 35.0,
    't_2q_ns': 660.0,
    'p_meas':  0.015,
}

def build_noise_model(n_qubits: int = 8, params: dict = None) -> NoiseModel:
    p  = params or IBM_EAGLE_PARAMS
    nm = NoiseModel()

    t1 = p['t1_us'] * 1e-6
    # Fix: clamp T2 ≤ 2*T1 and use the CLAMPED value for both the model
    # and the printed summary so they stay consistent.
    t2 = min(p['t2_us'] * 1e-6, 2 * t1)
    t2_us_actual = t2 * 1e6   # convert back for display

    e1q = depolarizing_error(p['p1q'], 1).compose(
          thermal_relaxation_error(t1, t2, p['t_1q_ns'] * 1e-9))
    nm.add_all_qubit_quantum_error(e1q, ['h', 'x', 'y', 'z', 'rz', 'rx'])

    relax_2q = thermal_relaxation_error(t1, t2, p['t_2q_ns'] * 1e-9)
    e2q = depolarizing_error(p['p2q'], 2).compose(relax_2q.expand(relax_2q))
    nm.add_all_qubit_quantum_error(e2q, ['cx'])

    pe = p['p_meas']
    re = ReadoutError([[1 - pe, pe], [pe, 1 - pe]])
    for q in range(n_qubits):
        nm.add_readout_error(re, [q])

    print(f"\n  Noise Model (IBM Eagle r3 approximation):")
    print(f"    1Q gate error : {p['p1q']*100:.2f}%  |  gate time: {p['t_1q_ns']}ns")
    print(f"    2Q gate error : {p['p2q']*100:.2f}%  |  gate time: {p['t_2q_ns']}ns")
    # Fix: print the actual clamped T2, not the raw param value
    print(f"    T1={p['t1_us']}µs  T2={t2_us_actual:.1f}µs (clamped ≤2·T1)  |  Readout: {pe*100:.2f}%")

    return nm
