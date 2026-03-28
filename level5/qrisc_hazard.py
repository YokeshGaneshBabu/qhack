# qrisc_hazard.py
"""
Q-RISC++ Hazard Detection & Forwarding Unit
=============================================
Detects:
  1. RAW  - Read After Write (data hazard)
  2. CONTROL - measurement feedback dependency
  3. STRUCTURAL - topology violation (resolved pre-pipeline by compiler)

Forwarding (bypassing):
  Instead of always stalling 2 cycles for RAW hazards, forwarding
  passes the result directly from EX→ID or WB→ID, reducing stalls.

  Without forwarding: every dependent instruction = 2 stall cycles
  With forwarding:    most RAW hazards = 0 stalls (result forwarded)
  Exception: MEASURE→next cannot be forwarded (quantum collapse needed)
"""

class ForwardingUnit:
    """
    EX/WB → ID forwarding paths.
    In a real CPU: result bus connects EX output back to ID input mux.
    Here we track which qubit registers have "fresh" results available.

    Fix: track ALL qubits written by a producer (rd AND rs1 for CNOT,
    since CNOT is a 2-qubit gate that modifies both control and target).
    """
    def __init__(self):
        self.ex_result = {}   # {qubit_reg: pc}
        self.wb_result = {}   # {qubit_reg: pc}

    def _written_regs(self, instr) -> set:
        """Return the set of qubit registers written by this instruction."""
        if instr is None or instr.itype == 'N' or instr.opcode == 'MEASURE':
            return set()
        written = set()
        if instr.rd is not None:
            written.add(instr.rd)
        # CNOT (R-type) also modifies rs1 (target qubit)
        if instr.itype == 'R' and instr.rs1 is not None:
            written.add(instr.rs1)
        return written

    def update(self, ex_instr, wb_instr):
        self.ex_result = {}
        self.wb_result = {}
        for reg in self._written_regs(ex_instr):
            self.ex_result[reg] = ex_instr.pc
        for reg in self._written_regs(wb_instr):
            # EX takes priority — don't overwrite with stale WB value
            if reg not in self.ex_result:
                self.wb_result[reg] = wb_instr.pc

    def can_forward(self, reg: int) -> tuple:
        """Returns (True, 'EX'/'WB') if forwarding is possible, else (False, None)."""
        if reg in self.ex_result:
            return True, 'EX'
        if reg in self.wb_result:
            return True, 'WB'
        return False, None


class HazardUnit:
    def __init__(self, topology, use_forwarding: bool = True):
        self.topology        = topology
        self.use_forwarding  = use_forwarding
        self.forwarding_unit = ForwardingUnit()
        self.stall_count     = 0
        self.forward_count   = 0
        self.hazard_log      = []

    def _reads_of(self, instr) -> set:
        """
        Return set of qubit registers READ by instr.
        Fix: FEEDBACK reads rd (to conditionally write it) so it's
        both a read and write — include it. Also covers all R/U/I/M types.
        """
        reads = set()
        if instr is None or instr.itype == 'N':
            return reads
        # R-type (CNOT): rd=control (read+write), rs1=target (read+write)
        if instr.itype == 'R':
            if instr.rd  is not None: reads.add(instr.rd)
            if instr.rs1 is not None: reads.add(instr.rs1)
        # U-type (H/X/Y/Z): rd is read then overwritten
        elif instr.itype == 'U':
            if instr.rd is not None: reads.add(instr.rd)
        # I-type (RZ/RX): rd is read then overwritten
        elif instr.itype == 'I':
            if instr.rd is not None: reads.add(instr.rd)
        # M-type (MEASURE): rd qubit is read and collapsed
        elif instr.itype == 'M':
            if instr.rd is not None: reads.add(instr.rd)
        # F-type (FEEDBACK): rd qubit is conditionally written — still a read dep
        elif instr.itype == 'F':
            if instr.rd is not None: reads.add(instr.rd)
        return reads

    def detect(self, id_instr, ex_instr, wb_instr) -> dict:
        """
        Check instruction in ID stage for hazards.
        Returns dict: {stall, type, reason, forwarded_from}
        """
        self.forwarding_unit.update(ex_instr, wb_instr)

        if id_instr is None or id_instr.itype == 'N':
            return {'stall': False, 'type': None, 'reason': None, 'fwd': None}

        reads = self._reads_of(id_instr)

        # ── RAW hazard check ──────────────────────────────────────────────────
        for producer in [ex_instr, wb_instr]:
            if producer is None or producer.itype == 'N':
                continue
            if producer.rd is None:
                continue

            # Check ALL registers written by this producer
            written_by_producer = self.forwarding_unit._written_regs(producer)
            # Also include MEASURE's rd (not in _written_regs since we excluded it,
            # but we still need to detect the RAW — just can't forward it)
            if producer.opcode == 'MEASURE' and producer.rd is not None:
                written_by_producer = {producer.rd}

            overlap = reads & written_by_producer
            if not overlap:
                continue

            # ── MEASURE results can NEVER be forwarded ────────────────────────
            if producer.opcode == 'MEASURE':
                reason = (f"RAW(no-fwd): QR{producer.rd} measured "
                          f"@PC{producer.pc}, read by {id_instr.opcode}@PC{id_instr.pc}")
                return {'stall': True, 'type': 'RAW', 'reason': reason, 'fwd': None}

            # ── Try forwarding ────────────────────────────────────────────────
            if self.use_forwarding:
                # Try to forward all overlapping registers
                fwd_regs = []
                for reg in overlap:
                    can_fwd, fwd_from = self.forwarding_unit.can_forward(reg)
                    if can_fwd:
                        fwd_regs.append((reg, fwd_from))

                if len(fwd_regs) == len(overlap):  # all reads can be forwarded
                    self.forward_count += 1
                    fwd_str = ', '.join(f"QR{r} from {f}" for r, f in fwd_regs)
                    return {'stall': False, 'type': 'RAW_FORWARDED',
                            'reason': fwd_str, 'fwd': fwd_regs[0][1]}

            # ── No forwarding possible → stall ────────────────────────────────
            reg = next(iter(overlap))
            reason = (f"RAW: QR{reg} written by "
                      f"{producer.opcode}@PC{producer.pc}, "
                      f"read by {id_instr.opcode}@PC{id_instr.pc}")
            return {'stall': True, 'type': 'RAW', 'reason': reason, 'fwd': None}

        # ── CONTROL hazard: FEEDBACK depends on MEASURE result in CR ─────────
        if id_instr.itype == 'F':
            for producer in [ex_instr, wb_instr]:
                if producer is None or producer.itype == 'N':
                    continue
                # Fix: guard crd is not None before comparing to avoid
                # accidental match when crd=None on non-MEASURE instructions
                if (producer.itype == 'M'
                        and producer.crd is not None
                        and producer.crd == id_instr.crs):
                    reason = (f"CONTROL: FEEDBACK@PC{id_instr.pc} needs "
                              f"CR{id_instr.crs} from MEASURE@PC{producer.pc}")
                    return {'stall': True, 'type': 'CONTROL',
                            'reason': reason, 'fwd': None}

        return {'stall': False, 'type': None, 'reason': None, 'fwd': None}

    def log_hazard(self, cycle: int, hazard: dict, instr):
        entry = {
            'cycle':  cycle,
            'type':   hazard['type'],
            'reason': hazard['reason'],
            'instr':  instr.asm() if instr else '?'
        }
        self.hazard_log.append(entry)
        self.stall_count += 1

    def print_summary(self, total_cycles: int, total_instrs: int):
        useful = total_instrs
        cpi = total_cycles / max(useful, 1)
        print(f"\n  ┌─────────────────────────────────────────────────┐")
        print(f"  │         Q-RISC++ PIPELINE STATISTICS            │")
        print(f"  ├─────────────────────────────────────────────────┤")
        print(f"  │  Total cycles        : {total_cycles:<24}│")
        print(f"  │  Instructions issued : {useful:<24}│")
        print(f"  │  CPI (cycles/instr)  : {cpi:<24.2f}│")
        print(f"  │  Stalls inserted     : {self.stall_count:<24}│")
        print(f"  │  Forwards (bypassed) : {self.forward_count:<24}│")
        stalls_avoided = self.forward_count
        print(f"  │  Stalls avoided(fwd) : {stalls_avoided:<24}│")
        print(f"  ├─────────────────────────────────────────────────┤")
        if self.hazard_log:
            print(f"  │  Hazard Log:                                    │")
            for e in self.hazard_log:
                t = f"Cy{e['cycle']:2d} [{e['type']:<8}]"
                print(f"  │  {t} {e['reason'][:35]:<35}│")
        print(f"  └─────────────────────────────────────────────────┘")
