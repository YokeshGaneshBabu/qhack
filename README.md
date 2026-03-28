# ⚛️ Q-Hack — Levels 1–5

> A complete end-to-end quantum computing project spanning reversible circuit design, combinational quantum logic, qubit state analysis, quantum cryptography, and a full quantum processor architecture — built with **Qiskit** and **QuTiP**.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Level 1 — 4-bit Ripple Carry Adder](#level-1--4-bit-ripple-carry-adder)
- [Level 2 — Smart City Emergency MUX](#level-2--smart-city-emergency-mux)
- [Level 3 — Bloch Sphere State Analysis](#level-3--bloch-sphere-state-analysis)
- [Level 4 — BB84 Quantum Key Distribution](#level-4--bb84-quantum-key-distribution)
- [Level 5 — Q-RISC++ Quantum Processor](#level-5--q-risc-quantum-processor)
- [Results Summary](#results-summary)
- [Setup & Installation](#setup--installation)
- [Project Structure](#project-structure)

---

## Overview

| Level | Challenge | Framework | Key Metric |
|-------|-----------|-----------|------------|
| 1 | 4-bit Reversible Ripple Carry Adder | Qiskit / Aer | 100% accuracy · 256 test cases |
| 2 | Smart City Priority MUX (4 sensors) | Qiskit / Aer | 100% accuracy · 16 test cases |
| 3 | Bloch Sphere — orthogonality proof | QuTiP | Tr(ρ₁ρ₂) = 0 verified |
| 4 | BB84 with adaptive eavesdropper | Qiskit / Aer | Eve detected above QBER > 11% |
| 5 | Q-RISC++ quantum processor | Qiskit / Aer | CPI 1.44 · 93.6% fidelity |

---

## Level 1 — 4-bit Ripple Carry Adder

**Task:** Design and implement a 4-bit Ripple Carry Adder (RCA) as a reversible quantum circuit using appropriate quantum gates.

Two implementations were developed and compared:

### Standard RCA (`4bitrca.py`)

Translates the classical full adder into reversible quantum logic using **CNOT** and **Toffoli (CCX)** gates. Each bit stage computes sum (3 CX) and carry-out (3 CCX) independently.

```
Qubit layout (17 qubits):
  q0–q3   : Input A (LSB → MSB)
  q4–q7   : Input B (LSB → MSB)
  q8–q11  : Sum outputs
  q12     : Carry-in (|0⟩)
  q13–q15 : Intermediate carries
  q16     : Final carry-out
```

| Property | Value |
|----------|-------|
| Qubits | 17 |
| Total 2-qubit gates | 36 (24 CX + 12 CCX) |
| Test cases | 256 (all 4×4-bit combos) |
| Accuracy | **100%** |

### Cuccaro RCA (`4bitrca_cuccoro.py`)

Implements the **Cuccaro et al. (2004)** in-place adder using MAJ (Majority) and UMA (UnMajority-and-Add) gate families. The carry propagates forward through MAJ and uncomputes backward through UMA, leaving the sum in the B register.

```
Qubit layout (10 qubits):
  q0      : Ancilla carry workspace
  q1–q4   : Input A
  q5–q8   : Input B → becomes Sum after computation
  q9      : Carry-out
```

| Property | Standard RCA | Cuccaro RCA |
|----------|-------------|-------------|
| Qubits | 17 | **10** (−41%) |
| 2-qubit gates | 36 | **20** (−44%) |
| In-place | ✗ | ✓ |
| Accuracy | 100% | 100% |

> **Cuccaro is recommended for NISQ hardware** — fewer qubits and gates means less decoherence exposure.

---

## Level 2 — Smart City Emergency MUX

**Task:** A smart city deploys 4 sensors (Medical, Fire, Gas, Intrusion). Due to limited bandwidth, design a combinational quantum circuit using a Priority MUX to intelligently select which emergency signal to transmit.

### Priority Order

```
Medical (I3)  >  Fire (I0)  >  Gas (I1)  >  Intrusion (I2)
  S1=0,S0=0      S1=0,S0=1    S1=1,S0=0     S1=1,S0=1
```

### Boolean Expressions

```
S1 = ~I3 & ~I0
S0 = (~I3 & I0) | (~I3 & ~I0 & ~I1)
Y  = (~S1&~S0&I3) | (~S1&S0&I0) | (S1&~S0&I1) | (S1&S0&I2)
```

The circuit uses **reversible AND** (Toffoli) with ancilla uncomputation to preserve circuit reversibility throughout. All 16 input combinations verified correct.

| Metric | Value |
|--------|-------|
| Circuit qubits | 12 (including 4 ancilla) |
| Test cases | 16 |
| Accuracy | **100%** |

---

## Level 3 — Bloch Sphere State Analysis

**Task:** Two students prepare:

$$|\psi_1\rangle = \frac{|0\rangle + |1\rangle}{\sqrt{2}} \qquad |\psi_2\rangle = \frac{|0\rangle - |1\rangle}{\sqrt{2}}$$

They claim: *"Both states look similar on the Bloch Sphere!"* — verify, visualize, and explain using QuTiP.

### Proof via Density Matrices

No statevectors used — proof relies entirely on `ρ = ½(I + r·σ)`:

```python
rho1 = qt.Qobj([[0.5,  0.5], [ 0.5, 0.5]])   # +X state
rho2 = qt.Qobj([[0.5, -0.5], [-0.5, 0.5]])   # −X state

overlap = (rho1 * rho2).tr().real
# → Tr(ρ₁ρ₂) = 0.000000  ✓ orthogonal
```

### Expectation Values

| State | ⟨σx⟩ | ⟨σy⟩ | ⟨σz⟩ | Bloch Position |
|-------|------|------|------|----------------|
| ρ₁ | +1.000 | 0.000 | 0.000 | Equator, +X axis |
| ρ₂ | −1.000 | 0.000 | 0.000 | Equator, −X axis |

### Verdict

The students' claim is **partially correct**:
- ✅ **Similar:** Both lie on the equatorial plane (rz = 0), same "altitude"
- ❌ **Different:** They point in opposite directions — antipodal, 180° apart
- 🔬 **Proof:** `Tr(ρ₁ρ₂) = 0` → maximally orthogonal states

---

## Level 4 — BB84 Quantum Key Distribution

**Task:** Implement a modified BB84 protocol where the quantum channel has intrinsic noise, and Eve performs an **adaptive attack** — adjusting her interception rate based on observed QBER to remain undetected.

### Simulation Parameters

```python
N_QUBITS       = 300      # qubits per batch
N_BATCHES      = 25       # simulation rounds
NOISE_PROB     = 0.03     # depolarizing noise on H, X, measure
QBER_THRESHOLD = 0.11     # detection boundary
EVE_INITIAL_F  = 0.30     # Eve starts intercepting 30% of qubits
EVE_STEP       = 0.04     # adaptive step size
SAMPLE_FRAC    = 0.25     # fraction used for QBER estimation
```

### Eve's Adaptive Strategy

```
1. Intercept-resend attack on random basis
2. Observe QBER after each batch
3. If QBER → threshold: reduce intercept fraction
4. Goal: extract max information while staying hidden
```

### Results

| Scenario | QBER | Eve Status |
|----------|------|-----------|
| Channel noise only | ~3% | No Eve |
| Eve at 30% intercept | ~14% | **Detected** (> 11%) |
| Eve adapted to ~18% | ~9–11% | Near boundary |

> **Key finding:** BB84 guarantees detection — any intercept rate that extracts meaningful key bits inevitably pushes QBER above the noise floor.

### Plots Generated

- `plot1_qber.png` — QBER over batches
- `plot2_eve_fraction.png` — Eve's adaptive intercept rate
- `plot3_expected_vs_observed.png` — Expected vs. actual QBER
- `plot4_key_bits.png` — Sifted key bits per batch

---

## Level 5 — Q-RISC++ Quantum Processor

**Task:** Design a next-generation quantum processor architecture inspired by RISC-V (called **Q-RISC++**) that executes a quantum program under real-world constraints.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Q-RISC++ v2.0                        │
│         A RISC-V Inspired Quantum CPU Architecture      │
├──────────┬──────────┬──────────┬──────────┬────────────┤
│    IF    │    ID    │    EX    │    WB    │  Pipeline  │
│ Fetch PC │ Decode   │ Gate +   │ Measure  │  4-stage   │
│          │ operands │ SWAP     │ & WB     │            │
├──────────┴──────────┴──────────┴──────────┴────────────┤
│  Qubit Topology: QR0 — QR1 — QR2 — QR3 (linear chain) │
│  Noise Model: IBM Eagle r3 approximation               │
└─────────────────────────────────────────────────────────┘
```

### Instruction Set Architecture

32-bit fixed-width encoding (RISC-V style):

| Type | Operations | Example |
|------|-----------|---------|
| R-type | Two-qubit register ops | `CNOT QR0, QR1` |
| I-type | Single-qubit + immediate | `RZ QR3, π/4` |
| U-type | Unitary single-qubit | `H QR0` |
| M-type | Measure to classical | `MEASURE QR0 → CR0` |
| F-type | Classical feedback | `FEEDBACK QR2 ← CR1` |

### Real-World Constraints Handled

- **Limited qubit connectivity** — linear chain topology; non-adjacent CNOTs auto-routed via SWAP insertion
- **Gate errors & decoherence** — IBM Eagle r3 noise (CX error 1%, measure error 1.5%, T1=100µs)
- **Measurement feedback** — classical bits control subsequent quantum gates
- **Instruction hazards** — RAW and CONTROL hazards detected and resolved

### Benchmark Program (16 instructions)

```
H    QR0          → superposition
CNOT QR0, QR1     → entanglement (adjacent)
CNOT QR0, QR3     → non-adjacent → SWAP routing triggered
MEASURE QR0 → CR0
FEEDBACK QR2 ← CR1
RZ QR3, π/4
...
```

### Performance Results

| Metric | With Forwarding | Without Forwarding |
|--------|----------------|-------------------|
| Total cycles | **23** | 43 |
| CPI | **1.438** | 2.688 |
| Pipeline stalls | **4** | 24 |
| Forwards bypassed | 10 | 0 |
| Fidelity (noisy) | 93.6% | 93.61% |
| **Speedup** | **1.87×** | — |

> Forwarding eliminates 20 RAW stalls, reducing CPI from 2.69 → 1.44. Control hazards (measurement feedback) still require 2 stall cycles each — unavoidable with classical latency.

---

## Results Summary

| Level | Implementation | Accuracy / Key Result |
|-------|---------------|----------------------|
| 1a | Standard 4-bit RCA (17 qubits) | ✅ 100% — 256/256 |
| 1b | Cuccaro RCA (10 qubits, −41%) | ✅ 100% — 256/256 |
| 2 | Smart City Priority MUX | ✅ 100% — 16/16 |
| 3 | Bloch Sphere orthogonality | ✅ Tr(ρ₁ρ₂) = 0 proven |
| 4 | BB84 + adaptive Eve | ✅ Eve detected at QBER > 11% |
| 5 | Q-RISC++ processor | ✅ CPI 1.44 · 93.6% fidelity |

---

## Setup & Installation

### Prerequisites

```bash
python >= 3.9
```

### Install Dependencies

```bash
pip install qiskit qiskit-aer qutip numpy pandas matplotlib
```

### Run Each Level

```bash
# Level 1 — Standard RCA
python level_1/4bitrca.py

# Level 1 — Cuccaro RCA
python level_1/4bitrca_cuccoro.py

# Level 2 — Smart City MUX
python level_2/priority_mux.py

# Level 3 — Bloch Sphere
python level_3/bloch_states.py

# Level 4 — BB84
python level_4/bb84.py

# Level 5 — Q-RISC++
python level_5/main.py
```

All outputs (circuits, histograms, heatmaps, plots) are saved to the respective `outputs_*/` directories.

---

## Project Structure

```
quantum-hackathon/
├── level_1/
│   ├── 4bitrca.py                        # Standard 17-qubit RCA
│   ├── 4bitrca_cuccoro.py                # Cuccaro 10-qubit RCA
│   └── outputs_qhack/
│       ├── rca_circuit.png
│       ├── rca_histogram.png
│       ├── rca_heatmap.png
│       └── rca_truth_table.csv
│   └── outputs_qhack_cuccoroo/
│       ├── cuccaro_circuit.png
│       ├── cuccaro_histogram.png
│       ├── cuccaro_heatmap.png
│       └── cuccaro_truth_table.csv
├── level_2/
│   ├── priority_mux.py
│   └── outputs_priority_mux/
│       ├── priority_mux_circuit.png
│       ├── priority_mux_histogram.png
│       ├── priority_mux_heatmap.png
│       └── priority_mux_truth_table.csv
├── level_3/
│   ├── bloch_states.py
│   └── outputs_bloch/
│       └── bloch_states.png
├── level_4/
│   ├── bb84.py
│   └── outputs_bb84/
│       ├── plot1_qber.png
│       ├── plot2_eve_fraction.png
│       ├── plot3_expected_vs_observed.png
│       └── plot4_key_bits.png
└── level_5/
    ├── main.py
    ├── qrisc_pipeline.py                 # 4-stage pipeline engine
    ├── qrisc_isa.py                      # 32-bit ISA encoding
    ├── qrisc_hazard.py                   # RAW & CONTROL hazard detection
    ├── qrisc_noise.py                    # IBM Eagle r3 noise model
    ├── qrisc_topology.py                 # Linear chain + SWAP routing
    └── outputs_risc/
        ├── qrisc_with_forwarding_circuit.png
        ├── qrisc_with_forwarding_histogram.png
        ├── qrisc_with_forwarding_pipeline_diagram.png
        ├── qrisc_with_forwarding_results.json
        ├── qrisc_no_forwarding_circuit.png
        ├── qrisc_no_forwarding_histogram.png
        ├── qrisc_no_forwarding_pipeline_diagram.png
        └── qrisc_no_forwarding_results.json
```

---

## References

- Cuccaro, S. A., Draper, T. G., Kutin, S. A., & Moulton, D. P. (2004). *A new quantum ripple-carry addition circuit.* arXiv:quant-ph/0410184
- Bennett, C. H., & Brassard, G. (1984). *Quantum cryptography: Public key distribution and coin tossing.* ICASSP.
- Patterson, D. A., & Hennessy, J. L. *Computer Organization and Design* (RISC-V Edition).
- [Qiskit Documentation](https://docs.quantum.ibm.com/)
- [QuTiP Documentation](https://qutip.org/docs/latest/)

---

*Built for a quantum computing hackathon — Yokesh G, March 2026*
