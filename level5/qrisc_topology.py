# qrisc_topology.py
"""
Q-RISC++ Hardware Topology
===========================
Linear chain: Q0—Q1—Q2—Q3—...
Only adjacent qubits can perform 2-qubit gates directly.
Non-adjacent → compiler inserts SWAP chain (pre-pipeline pass).
"""

def build_linear_topology(n: int) -> set:
    pairs = set()
    for i in range(n - 1):
        pairs.add((i, i + 1))
        pairs.add((i + 1, i))
    return pairs

def check_adjacent(q0: int, q1: int, topology: set) -> bool:
    return (q0, q1) in topology

def swap_chain_instrs(q0: int, q1: int) -> list:
    """
    Returns list of (ctrl, tgt) pairs for CNOT gates that implement
    SWAP routing to bring q0's logical state adjacent to q1 on a linear chain,
    then perform the final CNOT.

    SWAP(a,b) = CX(a,b) · CX(b,a) · CX(a,b)

    Fix: the original code built a path and appended ops for indices [0..n-3],
    then appended path[-2],path[-1] as the final CNOT.  That is correct only
    when q0 < q1 AND we want the last SWAP to end at (q1-1, q1).
    However it forgot to also insert SWAPs for the LAST pair (path[-2],path[-1])
    before the final CNOT — the loop stopped one pair too early.

    Correct approach: SWAP along every consecutive pair from q0 toward q1 to
    bubble q0's state to q1-1, then do the final CX(q1-1, q1).
    """
    if abs(q0 - q1) <= 1:
        return [(q0, q1)]

    lo, hi = min(q0, q1), max(q0, q1)
    path = list(range(lo, hi + 1))   # e.g. [0,1,2,3] for q0=0,q1=3

    ops = []
    # SWAP q0's state along the path until it is one step away from q1
    # i.e. perform SWAP(path[k], path[k+1]) for k in 0 .. len(path)-3
    for k in range(len(path) - 2):
        a, b = path[k], path[k + 1]
        ops += [(a, b), (b, a), (a, b)]   # SWAP via 3 CX

    # Now q0's logical state is at path[-2]; do the final CX
    ops.append((path[-2], path[-1]))
    return ops

def print_topology(n: int, topology: set):
    print(f"\n  Hardware Topology ({n} qubits, linear chain):")
    print("  " + " ─── ".join([f"Q{i}" for i in range(n)]))
    print(f"  Allowed 2Q pairs: {sorted((a, b) for a, b in topology if a < b)}")
