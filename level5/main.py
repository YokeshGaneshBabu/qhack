# main.py
"""
Q-RISC++ Processor — Full Demo
================================
Demonstrates all Level-5 requirements:
  ✓ Next-gen quantum processor inspired by RISC-V
  ✓ 32-bit ISA encoding (R/I/U/M/F types)
  ✓ 4-stage pipeline (IF/ID/EX/WB)
  ✓ Limited qubit connectivity (linear topology + SWAP routing)
  ✓ Gate errors & decoherence (IBM Eagle noise model)
  ✓ Measurement feedback (conditional gate)
  ✓ Instruction hazards (RAW, CONTROL + forwarding unit)
  ✓ CPI metric, fidelity score, pipeline diagram
"""

import math
from qrisc_pipeline import QRISCPipeline

print("=" * 68)
print("  Q-RISC++ QUANTUM PROCESSOR  —  v2.0")
print("  A RISC-V Inspired Quantum CPU Architecture")
print("=" * 68)

# ══════════════════════════════════════════════════════════════════════════════
#  PROGRAM: Written in Q-RISC++ assembly (as dicts, like writing .s files)
#
#  This program demonstrates:
#  1. Superposition  → H QR0
#  2. Entanglement   → CNOT QR0, QR1
#  3. Topology test  → CNOT QR0, QR3  (non-adjacent! triggers SWAP routing)
#  4. RAW hazard     → CNOT right after H (same qubit)
#  5. Measurement    → MEASURE QR0 → CR0
#  6. Feedback       → FEEDBACK QR2 ← CR1 (classical bit controls quantum gate)
#  7. Rotation       → RZ QR3, π/4
# ══════════════════════════════════════════════════════════════════════════════

program = [
    # ── Superposition + Entanglement ──────────────────────────────────────
    # PC=0: H QR0          → |0⟩ → |+⟩
    dict(opcode='H',        itype='U', rd=0,                label='superpose Q0'),

    # PC=1: CNOT QR0,QR1   → entangle Q0,Q1 (adjacent ✓)
    dict(opcode='CNOT',     itype='R', rd=0, rs1=1,         label='entangle Q0,Q1'),

    # PC=2: CNOT QR0,QR3   → NON-ADJACENT (Q0 and Q3 not connected)
    #                         Compiler will insert SWAP chain automatically
    dict(opcode='CNOT',     itype='R', rd=0, rs1=3,         label='non-adj CNOT → SWAP'),

    # ── Measurement ───────────────────────────────────────────────────────
    # PC=3: MEASURE QR0 → CR0
    dict(opcode='MEASURE',  itype='M', rd=0, crd=0,         label='measure Q0'),

    # PC=4: H QR0  ← RAW hazard: QR0 just measured above
    dict(opcode='H',        itype='U', rd=0,                label='RAW hazard test'),

    # PC=5: MEASURE QR1 → CR1
    dict(opcode='MEASURE',  itype='M', rd=1, crd=1,         label='measure Q1'),

    # ── Classical Feedback ────────────────────────────────────────────────
    # PC=6: FEEDBACK QR2 ← CR1  → control hazard: needs CR1 from above
    dict(opcode='FEEDBACK', itype='F', rd=2, crs=1,         label='feedback Q2←CR1'),

    # PC=7: MEASURE QR2 → CR2
    dict(opcode='MEASURE',  itype='M', rd=2, crd=2,         label='measure Q2'),

    # ── Rotation + Final Measure ──────────────────────────────────────────
    # PC=8: RZ QR3, π/4
    dict(opcode='RZ',       itype='I', rd=3, imm=math.pi/4, label='rotate Q3'),

    # PC=9: MEASURE QR3 → CR3
    dict(opcode='MEASURE',  itype='M', rd=3, crd=3,         label='measure Q3'),
]

# ── Run with forwarding ON (default — fewer stalls) ───────────────────────────
print("\n▶  Run 1: With Forwarding/Bypassing Unit ENABLED")
print("─" * 68)
cpu_fwd = QRISCPipeline(n_qubits=4, use_noise=True, use_forwarding=True)
cpu_fwd.load_program(program)
noisy, ideal, fidelity = cpu_fwd.run(shots=4096, program_name="qrisc_with_forwarding")

# ── Run without forwarding (for comparison — shows stall difference) ──────────
print("\n\n▶  Run 2: Without Forwarding (baseline — more stalls)")
print("─" * 68)
cpu_nofwd = QRISCPipeline(n_qubits=4, use_noise=True, use_forwarding=False)
cpu_nofwd.load_program(program)
cpu_nofwd.run(shots=4096, program_name="qrisc_no_forwarding")

# ── Final summary ─────────────────────────────────────────────────────────────
print("\n" + "=" * 68)
print("  FINAL COMPARISON SUMMARY")
print("=" * 68)
print(f"  With forwarding    : {cpu_fwd.cycle} cycles,   "
      f"{cpu_fwd.hazard_unit.stall_count} stalls,  "
      f"{cpu_fwd.hazard_unit.forward_count} bypasses")
print(f"  Without forwarding : {cpu_nofwd.cycle} cycles, "
      f"{cpu_nofwd.hazard_unit.stall_count} stalls,  "
      f"0 bypasses")
print(f"  Stalls saved by forwarding: "
      f"{cpu_nofwd.hazard_unit.stall_count - cpu_fwd.hazard_unit.stall_count}")
print(f"  Fidelity: {fidelity*100:.1f}%  |  Noise degradation: {(1-fidelity)*100:.1f}%")
print(f"\n  All outputs saved to: C:\\Users\\Yokesh G\\qiskit-project\\outputs_risc\\")
print("=" * 68)
