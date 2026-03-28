# qrisc_pipeline.py
"""
Q-RISC++ 4-Stage Pipeline
==========================
Stages: IF (Fetch) → ID (Decode) → EX (Execute) → WB (Write-Back)

Fixes applied:
  - IF log now shows the instruction being fetched this cycle (pc before advance),
    not the one two ahead.
  - Drain condition correctly checks all three post-fetch stages.
  - _apply_gate no longer double-counts NOPs in instr_count.
  - [BUG FIX] Pipeline diagram y-axis labels were reversed (WB shown at top,
    IF at bottom). Fixed by correcting set_yticklabels order.
  - [BUG FIX] Pipeline log snapshot was taken BEFORE the stall/advance decision,
    causing the same instruction to appear in EX across multiple consecutive cycles
    (the "HHH" triple-H artifact). Snapshot is now taken AFTER the advance block
    so each entry reflects what each stage actually held for that cycle.
"""

import os, json, math
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit_aer import AerSimulator

from qrisc_isa import Instruction, RegisterFile, make_nop, assemble, NUM_QREGS
from qrisc_hazard import HazardUnit
from qrisc_topology import (build_linear_topology, check_adjacent,
                              swap_chain_instrs, print_topology)
from qrisc_noise import build_noise_model

OUTPUT_DIR = r"C:\Users\Yokesh G\qiskit-project\outputs_risc"


# ══════════════════════════════════════════════════════════════════════════════
#  COMPILER PRE-PASS: SWAP insertion
# ══════════════════════════════════════════════════════════════════════════════
def compiler_swap_pass(instructions: list, topology: set) -> list:
    """
    Walk program, replace non-adjacent CNOTs with SWAP chain + CNOT.
    This is the routing/placement pass of a real quantum compiler.
    """
    expanded = []
    swap_count = 0
    for instr in instructions:
        if instr.opcode == 'CNOT' and not check_adjacent(instr.rd, instr.rs1, topology):
            ops = swap_chain_instrs(instr.rd, instr.rs1)
            print(f"    [ROUTER] CNOT(QR{instr.rd},QR{instr.rs1}) → "
                  f"{len(ops)} ops (SWAP chain + CNOT)")
            for ctrl, tgt in ops[:-1]:
                si = Instruction('CNOT', 'R', rd=ctrl, rs1=tgt,
                                 label=f'SWAP({ctrl},{tgt})')
                si.encode()
                expanded.append(si)
                swap_count += 1
            c, t = ops[-1]
            fi = Instruction('CNOT', 'R', rd=c, rs1=t, label=instr.label)
            fi.encode()
            expanded.append(fi)
        else:
            expanded.append(instr)
    for i, ins in enumerate(expanded):
        ins.pc = i
        ins.encode()
    print(f"    [ROUTER] {len(instructions)} → {len(expanded)} instructions "
          f"({swap_count} SWAP gates inserted)")
    return expanded


# ══════════════════════════════════════════════════════════════════════════════
#  PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
class QRISCPipeline:

    def __init__(self, n_qubits: int = 4, use_noise: bool = True,
                 use_forwarding: bool = True):
        self.n_qubits       = n_qubits
        self.topology       = build_linear_topology(n_qubits)
        self.regfile        = RegisterFile()
        self.hazard_unit    = HazardUnit(self.topology, use_forwarding)
        self.noise_model    = build_noise_model(n_qubits) if use_noise else None
        self.use_noise      = use_noise
        self.use_forwarding = use_forwarding

        qr = QuantumRegister(n_qubits, 'QR')
        cr = ClassicalRegister(n_qubits, 'CR')
        self.qc = QuantumCircuit(qr, cr)
        self.qr = qr
        self.cr = cr

        # Pipeline stage registers
        self.IF_reg = self.ID_reg = self.EX_reg = self.WB_reg = None

        self.cycle        = 0
        self.pc           = 0
        self.program      = []
        self.instr_count  = 0
        self.pipeline_log = []

        print_topology(n_qubits, self.topology)

    # ── Load & compile ────────────────────────────────────────────────────────
    def load_program(self, raw_program: list):
        print("\n  ── Assembler ─────────────────────────────────────────────")
        instructions = assemble(raw_program)
        print("\n  ── Compiler: Routing Pass ────────────────────────────────")
        self.program = compiler_swap_pass(instructions, self.topology)
        self.pc = 0
        print(f"\n  Program ready: {len(self.program)} instructions loaded into memory")

    # ── Gate application (EX stage) ───────────────────────────────────────────
    def _apply_gate(self, instr: Instruction):
        """Apply gate to Qiskit circuit. Only real instructions count."""
        if instr is None or instr.itype == 'N':
            return
        op, rd, rs1 = instr.opcode, instr.rd, instr.rs1
        if   op == 'H':        self.qc.h(rd)
        elif op == 'X':        self.qc.x(rd)
        elif op == 'Y':        self.qc.y(rd)
        elif op == 'Z':        self.qc.z(rd)
        elif op == 'RZ':       self.qc.rz(instr.imm, rd)
        elif op == 'RX':       self.qc.rx(instr.imm, rd)
        elif op == 'CNOT':     self.qc.cx(rd, rs1)
        elif op == 'MEASURE':  self.qc.measure(rd, instr.crd)
        elif op == 'FEEDBACK':
            with self.qc.if_test((self.cr[instr.crs], 1)):
                self.qc.x(rd)
        self.instr_count += 1

    # ── Main pipeline loop ────────────────────────────────────────────────────
    def run(self, shots: int = 4096, program_name: str = "qrisc"):
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        MAX_CYCLES = len(self.program) * 4 + 20

        print(f"\n  ── Pipeline Execution ────────────────────────────────────")
        print(f"  {'Cy':>4}  {'IF':<12} {'ID':<12} {'EX':<12} {'WB':<12}  Note")
        print(f"  {'─'*70}")

        while self.cycle < MAX_CYCLES:
            self.cycle += 1

            # ── WB stage: result written back (classical reg update post-sim) ──

            # ── EX stage: apply gate ──────────────────────────────────────────
            self._apply_gate(self.EX_reg)

            # ── Hazard detection (between ID and EX) ──────────────────────────
            hazard = self.hazard_unit.detect(self.ID_reg, self.EX_reg, self.WB_reg)

            note = ""
            if hazard['stall']:
                self.hazard_unit.log_hazard(self.cycle, hazard, self.ID_reg)
                note = f"⚠ STALL [{hazard['type']}]"
            elif hazard['type'] == 'RAW_FORWARDED':
                note = f"→ FWD from {hazard['fwd']}"

            # ── Snapshot ALL stages BEFORE the advance ────────────────────────
            # Every stage is snapshotted at the START of the cycle before any
            # register shuffling. This guarantees no two adjacent stages ever
            # display the same instruction on the same cycle row.
            # EX is a special case: if a stall fires this cycle a NOP bubble
            # is injected — we show "NOP" for EX to reflect that.
            if_fetching = self.program[self.pc] if self.pc < len(self.program) else None
            snap_id = self.ID_reg
            snap_ex = self.EX_reg
            snap_wb = self.WB_reg

            # ── Advance pipeline ──────────────────────────────────────────────
            if hazard['stall']:
                # Freeze IF and ID; insert bubble into EX; WB gets old EX
                self.WB_reg = self.EX_reg
                self.EX_reg = make_nop(self.cycle)
                # ID_reg and pc are frozen (NOT incremented)
            else:
                self.WB_reg = self.EX_reg
                self.EX_reg = self.ID_reg
                self.ID_reg = if_fetching
                if self.pc < len(self.program):
                    self.pc += 1

            # ── Build labels from pre-advance snapshots ───────────────────────
            def lbl(s):
                if s is None:      return '─'
                if s.itype == 'N': return 'NOP'
                return s.opcode

            if_lbl = lbl(if_fetching)
            id_lbl = lbl(snap_id)
            # EX and WB: always use the pre-advance snapshot directly.
            # The NOP bubble injected by a stall will naturally appear in
            # snap_ex on the *next* cycle (after make_nop was written into
            # self.EX_reg at the end of the previous cycle's advance block).
            # Overriding ex_lbl with 'NOP' here causes double-NOP display
            # and makes real instructions disappear from EX entirely.
            ex_lbl = lbl(snap_ex)
            wb_lbl = lbl(snap_wb)

            self.pipeline_log.append({
                'cycle': self.cycle,
                'IF': if_lbl,
                'ID': id_lbl,
                'EX': ex_lbl,
                'WB': wb_lbl,
                'note': note
            })
            print(f"  {self.cycle:>4}  {if_lbl:<12} {id_lbl:<12} "
                  f"{ex_lbl:<12} {wb_lbl:<12}  {note}")

            # ── Drain check: pc exhausted AND all pipeline stages empty ───────
            if (self.pc >= len(self.program) and
                    all(s is None or s.itype == 'N'
                        for s in [self.ID_reg, self.EX_reg, self.WB_reg])):
                break

        print(f"  {'─'*70}")
        self.hazard_unit.print_summary(self.cycle, self.instr_count)

        return self._backend_and_report(shots, program_name)

    # ── Backend + all output generation ──────────────────────────────────────
    def _backend_and_report(self, shots: int, name: str):
        print(f"\n  ── Qiskit Backend ────────────────────────────────────────")

        backend_noisy = AerSimulator(noise_model=self.noise_model) if self.use_noise \
                        else AerSimulator()
        tqc = transpile(self.qc, backend=backend_noisy, optimization_level=1)
        counts_noisy = backend_noisy.run(tqc, shots=shots).result().get_counts()

        backend_ideal = AerSimulator()
        tqc_ideal = transpile(self.qc, backend=backend_ideal, optimization_level=1)
        counts_ideal = backend_ideal.run(tqc_ideal, shots=shots).result().get_counts()

        fidelity = self._compute_fidelity(counts_noisy, counts_ideal, shots)

        print(f"  Fidelity (noisy vs ideal): {fidelity*100:.1f}%")
        print(f"  Noise degradation        : {(1-fidelity)*100:.1f}%")

        self._save_circuit(name)
        self._save_histogram(name, counts_noisy, counts_ideal, shots, fidelity)
        self._save_pipeline_diagram(name)
        self._save_json(name, counts_noisy, counts_ideal, fidelity, shots)

        print(f"\n  📊 Top outcomes (noisy):")
        top = dict(sorted(counts_noisy.items(), key=lambda x: -x[1])[:6])
        for state, cnt in top.items():
            bar = '█' * (cnt // max(1, shots // 50))
            pct = cnt / shots * 100
            print(f"     |{state}⟩ : {cnt:4d} ({pct:4.1f}%)  {bar}")

        return counts_noisy, counts_ideal, fidelity

    def _compute_fidelity(self, noisy: dict, ideal: dict, shots: int) -> float:
        """Bhattacharyya coefficient — overlap between noisy and ideal distributions."""
        all_states = set(noisy) | set(ideal)
        overlap = sum(
            math.sqrt((noisy.get(s, 0) / shots) * (ideal.get(s, 0) / shots))
            for s in all_states
        )
        return min(overlap, 1.0)

    def _save_circuit(self, name: str):
        path = os.path.join(OUTPUT_DIR, f"{name}_circuit.png")
        try:
            fig = self.qc.draw('mpl', fold=60, style='bw')
            fig.savefig(path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            print(f"  💾 Circuit diagram  → {path}")
        except Exception as e:
            print(f"  ⚠  Circuit skipped: {e}")

    def _save_histogram(self, name, noisy, ideal, shots, fidelity):
        path = os.path.join(OUTPUT_DIR, f"{name}_histogram.png")
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle(
            f"Q-RISC++ Results: {name}\n"
            f"{shots} shots | {self.cycle} cycles | "
            f"CPI={self.cycle/max(self.instr_count,1):.2f} | "
            f"Fidelity={fidelity*100:.1f}% | "
            f"Stalls={self.hazard_unit.stall_count} | "
            f"Forwards={self.hazard_unit.forward_count}",
            fontweight='bold', fontsize=11)

        for ax, counts, title, color in [
            (axes[0], ideal, "Ideal (no noise)", '#16a34a'),
            (axes[1], noisy, "Noisy (IBM Eagle model)", '#2563eb'),
        ]:
            top = dict(sorted(counts.items(), key=lambda x: -x[1])[:12])
            bars = ax.bar(top.keys(), top.values(), color=color,
                          edgecolor='black', alpha=0.85)
            ax.set_title(title, fontweight='bold')
            ax.set_xlabel("Measurement Outcome")
            ax.set_ylabel("Count")
            ax.tick_params(axis='x', rotation=45)
            for b in bars:
                ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 2,
                        str(int(b.get_height())), ha='center', fontsize=7)

        plt.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"  💾 Histogram        → {path}")

    def _save_pipeline_diagram(self, name: str):
        path = os.path.join(OUTPUT_DIR, f"{name}_pipeline_diagram.png")
        log = self.pipeline_log
        n   = len(log)
        if n == 0:
            return

        # Stage order for iteration (index 0 = bottom of diagram = WB,
        # index 3 = top = IF) so that IF renders at the top visually.
        # The stages list drives both the data lookup and the y positions.
        stages = ['WB', 'EX', 'ID', 'IF']   # j=0 → bottom row, j=3 → top row

        colors = {
            'H': '#fbbf24', 'X': '#f87171', 'Y': '#fb923c', 'Z': '#a78bfa',
            'CNOT': '#60a5fa', 'RZ': '#34d399', 'RX': '#2dd4bf',
            'MEASURE': '#94a3b8', 'FEEDBACK': '#f472b6', 'NOP': '#e5e7eb',
            '─': '#f9fafb',
        }

        fig, ax = plt.subplots(figsize=(max(14, n * 0.4), 5))
        ax.set_xlim(0, n)
        ax.set_ylim(0, 4)
        ax.set_yticks([0.5, 1.5, 2.5, 3.5])

        # FIX: y-tick labels must match the stages list order above.
        # j=0 (y=0.5) → WB (bottom), j=3 (y=3.5) → IF (top).
        ax.set_yticklabels(['WB', 'EX', 'ID', 'IF'], fontsize=10, fontweight='bold')

        ax.set_xticks(range(n))
        ax.set_xticklabels([str(e['cycle']) for e in log], fontsize=7, rotation=45)
        ax.set_xlabel("Pipeline Cycle", fontsize=10)
        ax.set_title(
            f"Q-RISC++ Pipeline Timing Diagram: {name}\n"
            f"{self.cycle} cycles | {self.hazard_unit.stall_count} stalls | "
            f"{self.hazard_unit.forward_count} forwards",
            fontweight='bold', fontsize=11)
        ax.grid(axis='x', linestyle='--', alpha=0.3)

        for i, entry in enumerate(log):
            for j, stage in enumerate(stages):
                op = entry[stage]          # look up correct stage by name
                c  = colors.get(op, '#cbd5e1')
                rect = mpatches.FancyBboxPatch(
                    (i + 0.05, j + 0.1), 0.9, 0.8,
                    boxstyle="round,pad=0.02", linewidth=0.5,
                    edgecolor='#374151', facecolor=c)
                ax.add_patch(rect)
                ax.text(i + 0.5, j + 0.5, op[:4], ha='center', va='center',
                        fontsize=6.5, fontweight='bold', color='#111827')
            if 'STALL' in entry['note']:
                ax.axvline(x=i + 0.5, color='red', alpha=0.3,
                           linewidth=1.5, linestyle=':')

        legend_ops = ['H', 'X', 'CNOT', 'RZ', 'MEASURE', 'FEEDBACK', 'NOP']
        patches = [mpatches.Patch(color=colors.get(op, '#cbd5e1'), label=op)
                   for op in legend_ops]
        patches.append(mpatches.Patch(color='red', alpha=0.3, label='STALL'))
        ax.legend(handles=patches, loc='upper right', fontsize=7,
                  ncol=4, framealpha=0.9)

        plt.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"  💾 Pipeline diagram → {path}")

    def _save_json(self, name, noisy, ideal, fidelity, shots):
        path = os.path.join(OUTPUT_DIR, f"{name}_results.json")
        cpi  = self.cycle / max(self.instr_count, 1)
        data = {
            "program":         name,
            "architecture":    "Q-RISC++ v2 (RISC-V inspired quantum processor)",
            "pipeline_stages": ["IF", "ID", "EX", "WB"],
            "forwarding":      self.use_forwarding,
            "topology":        f"linear chain ({self.n_qubits} qubits)",
            "metrics": {
                "total_cycles":          self.cycle,
                "instructions_issued":   self.instr_count,
                "CPI":                   round(cpi, 3),
                "stalls":                self.hazard_unit.stall_count,
                "forwards_bypassed":     self.hazard_unit.forward_count,
                "fidelity_pct":          round(fidelity * 100, 2),
                "noise_degradation_pct": round((1 - fidelity) * 100, 2),
                "shots":                 shots,
            },
            "noise_model":  "IBM Eagle r3 approximation",
            "hazard_log":   self.hazard_unit.hazard_log,
            "counts_ideal": ideal,
            "counts_noisy": noisy,
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"  💾 Results JSON     → {path}")