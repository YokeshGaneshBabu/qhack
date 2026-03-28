import os
import pandas as pd
import matplotlib.pyplot as plt
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit.visualization import plot_histogram

OUT = r"C:\Users\Yokesh G\qiskit-project\outputs_qhack_cuccoroo"
os.makedirs(OUT, exist_ok=True)
sim = AerSimulator()

# ── MAJ gate ─────────────────────────────────────────────────────────────────
def maj(qc, a, b, c):
    qc.cx(c, b)
    qc.cx(c, a)
    qc.ccx(a, b, c)

# ── UMA gate ─────────────────────────────────────────────────────────────────
def uma(qc, a, b, c):
    qc.ccx(a, b, c)
    qc.cx(c, a)
    qc.cx(a, b)

# ── Cuccaro 4-bit RCA (10 qubits) ────────────────────────────────────────────
def cuccaro_4bit(A, B):
    """
    Qubit layout:
      q0      → ancilla (carry workspace, always starts/ends at 0)
      q1–q4   → A (LSB→MSB)
      q5–q8   → B (LSB→MSB) — becomes Sum after computation
      q9      → Cout

    Classical bits:
      c0–c3   → Sum (from q5–q8)
      c4      → Cout (from q9)
    """
    qc = QuantumCircuit(10, 5, name="Cuccaro 4-bit RCA")

    # Load inputs
    for i in range(4):
        if A[i]: qc.x(i + 1)   # A → q1,q2,q3,q4
        if B[i]: qc.x(i + 5)   # B → q5,q6,q7,q8

    qc.barrier(label="inputs")

    # MAJ cascade — carry propagates forward
    maj(qc, 0, 5, 1)   # stage 0: ancilla, B0, A0
    maj(qc, 1, 6, 2)   # stage 1: A0*, B1, A1
    maj(qc, 2, 7, 3)   # stage 2: A1*, B2, A2
    maj(qc, 3, 8, 4)   # stage 3: A2*, B3, A3

    qc.barrier(label="MAJ done / capture Cout")

    # Capture Cout into q9
    qc.cx(4, 9)

    qc.barrier(label="UMA starts")

    # UMA cascade — carry uncomputes, sum appears in B qubits
    uma(qc, 3, 8, 4)   # stage 3
    uma(qc, 2, 7, 3)   # stage 2
    uma(qc, 1, 6, 2)   # stage 1
    uma(qc, 0, 5, 1)   # stage 0

    qc.barrier(label="measure")

    # Sum is now in q5–q8, Cout in q9
    qc.measure([5, 6, 7, 8, 9], [0, 1, 2, 3, 4])
    return qc

# ── Decode (same logic as before) ────────────────────────────────────────────
def decode(out_str):
    # out_str: c4(Cout) c3(S3) c2(S2) c1(S1) c0(S0)  — MSB first
    final = int(out_str, 2)
    cout  = int(out_str[0])
    s_int = int(out_str[1:], 2)
    return final, cout, s_int

# ── Run ───────────────────────────────────────────────────────────────────────
def run_rca(A, B, shots=1024):
    qc     = cuccaro_4bit(A, B)
    tqc    = transpile(qc, sim)
    result = sim.run(tqc, shots=shots).result()
    counts = result.get_counts()
    best   = max(counts, key=counts.get)
    return qc, counts, best

# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════
A = [1, 0, 1, 1]   # 11 (LSB first)
B = [1, 1, 0, 1]   # 13

a_int = int("".join(map(str, A[::-1])), 2)
b_int = int("".join(map(str, B[::-1])), 2)

qc, counts, best = run_rca(A, B)
final, cout, s_int = decode(best)

print("=" * 40)
print(f"  Method   = Cuccaro (10 qubits)")
print(f"  A        = {A}  ({a_int})")
print(f"  B        = {B}  ({b_int})")
print(f"  Expected = {a_int + b_int}")
print(f"  Got      = {final}  (Sum={s_int}, Cout={cout})")
print(f"  Correct  = {final == a_int + b_int}")
print("=" * 40)

# ── Circuit diagram ───────────────────────────────────────────────────────────
fig = qc.draw("mpl", fold=40, style="iqp")
fig.suptitle("Cuccaro 4-bit RCA — 10 Qubits (MAJ+UMA)", fontsize=13, fontweight="bold")
fig.savefig(f"{OUT}\\cuccaro_circuit.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved: cuccaro_circuit.png")

# ── Histogram ─────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(6, 4))
plot_histogram(counts, ax=ax, title=f"Cuccaro — A={a_int}, B={b_int}, Expected={a_int+b_int}")
fig.tight_layout()
fig.savefig(f"{OUT}\\cuccaro_histogram.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved: cuccaro_histogram.png")

# ── Full truth table sweep ────────────────────────────────────────────────────
rows = []
print("\nRunning all 256 combinations...")
for a_i in range(16):
    for b_i in range(16):
        A_i = [(a_i >> i) & 1 for i in range(4)]
        B_i = [(b_i >> i) & 1 for i in range(4)]
        _, _, best_i = run_rca(A_i, B_i)
        got, _, _ = decode(best_i)
        rows.append({
            "A": a_i, "B": b_i,
            "Expected": a_i + b_i,
            "Got": got,
            "Pass": got == a_i + b_i
        })

df = pd.DataFrame(rows)
df.to_csv(f"{OUT}\\cuccaro_truth_table.csv", index=False)
acc = df["Pass"].mean() * 100
print(f"Accuracy: {acc:.1f}%")

# ── Heatmap ───────────────────────────────────────────────────────────────────
pivot = df.pivot(index="A", columns="B", values="Pass").astype(int)
fig, ax = plt.subplots(figsize=(7, 6))
im = ax.imshow(pivot, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
ax.set_xticks(range(16)); ax.set_yticks(range(16))
ax.set_xticklabels(range(16)); ax.set_yticklabels(range(16))
ax.set_xlabel("B"); ax.set_ylabel("A")
ax.set_title(f"Cuccaro 4-bit RCA — Pass/Fail  (Accuracy: {acc:.1f}%)", fontweight="bold")
plt.colorbar(im, ax=ax, ticks=[0, 1], label="0=Fail  1=Pass")
fig.tight_layout()
fig.savefig(f"{OUT}\\cuccaro_heatmap.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved: cuccaro_heatmap.png")

# ── Qubit comparison summary ──────────────────────────────────────────────────
print("\n── Qubit Comparison ──────────────────")
print("  Original (naive RCA) : 17 qubits")
print("  Cuccaro  (MAJ+UMA)   : 10 qubits")
print("  Reduction            : 7 qubits (41% fewer)")
print("─────────────────────────────────────")
print("\nDone. All outputs in:", OUT)
