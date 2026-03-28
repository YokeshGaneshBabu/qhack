# qrisc_isa.py
"""
Q-RISC++ Instruction Set Architecture
======================================
32-bit fixed-width instruction encoding (RISC-V style):

 31      25 24   20 19  15 14  12 11    7 6      0
┌──────────┬───────┬──────┬──────┬───────┬────────┐
│  funct7  │  rs2  │  rs1 │funct3│  rd   │ opcode │  R-type (2-qubit gates)
├──────────┴───────┴──────┴──────┴───────┴────────┤
│    imm[11:0]     │  rs1 │funct3│  rd   │ opcode │  I-type (rotation gates)
├──────────────────┴──────┴──────┴───────┴────────┤
│         imm[19:0]               │  rd   │ opcode │  U-type (single-qubit)
├─────────────────────────────────┴───────┴────────┤
│   crs/crd  │  qrs  │funct3 │  qrd  │   opcode   │  M/F-type (measure/feedback)
└────────────────────────────────────────────────┘

Register File:
  QR0–QR7  : 8 quantum registers (physical qubits)
  CR0–CR7  : 8 classical registers (measurement results)
  PC       : Program counter
"""

from dataclasses import dataclass, field
from typing import Optional
import struct

# ── Opcode table (7-bit, RISC-V style) ───────────────────────────────────────
OPCODES = {
    # opcode : (itype, funct3, description, latency_cycles)
    0b0000011: ('U', 0b000, 'H     - Hadamard',              1),
    0b0000111: ('U', 0b001, 'X     - Pauli-X (NOT)',         1),
    0b0001011: ('U', 0b010, 'Y     - Pauli-Y',               1),
    0b0001111: ('U', 0b011, 'Z     - Pauli-Z',               1),
    0b0010011: ('I', 0b000, 'RZ    - Rotate Z(angle)',       1),
    0b0010111: ('I', 0b001, 'RX    - Rotate X(angle)',       1),
    0b0110011: ('R', 0b000, 'CNOT  - Controlled-NOT',        2),
    0b0100011: ('M', 0b000, 'MEAS  - Measure qubit→creg',    1),
    0b1100011: ('F', 0b000, 'FDBK  - Classical feedback',    1),
    0b1110011: ('N', 0b000, 'NOP   - Pipeline bubble',       1),
}

# Reverse map: mnemonic → opcode int
MNEMONIC_TO_OPCODE = {
    'H': 0b0000011, 'X': 0b0000111, 'Y': 0b0001011, 'Z': 0b0001111,
    'RZ': 0b0010011, 'RX': 0b0010111,
    'CNOT': 0b0110011,
    'MEASURE': 0b0100011,
    'FEEDBACK': 0b1100011,
    'NOP': 0b1110011,
}

NUM_QREGS = 8
NUM_CREGS = 8


# ── Register File ─────────────────────────────────────────────────────────────
class RegisterFile:
    """
    Quantum register file with proper read/write ports (like a real CPU).
    Two read ports (rs1, rs2) + one write port (rd) per cycle.
    """
    def __init__(self):
        # QR0 is hardwired to qubit 0 (like x0=0 in RISC-V)
        self.qregs = list(range(NUM_QREGS))   # maps reg index → qubit index
        self.cregs = [0] * NUM_CREGS           # classical bit values
        self._write_pending = {}               # tracks in-flight writes

    def read_q(self, idx: int) -> int:
        assert 0 <= idx < NUM_QREGS, f"QR{idx} out of range"
        return self.qregs[idx]

    def read_c(self, idx: int) -> int:
        return self.cregs[idx]

    def write_c(self, idx: int, val: int):
        self.cregs[idx] = val & 1

    def mark_in_flight(self, rd: int, source_pc: int):
        """Track that rd is being written by instruction at source_pc."""
        self._write_pending[rd] = source_pc

    def clear_in_flight(self, rd: int):
        self._write_pending.pop(rd, None)

    def is_in_flight(self, reg: int) -> bool:
        return reg in self._write_pending

    def dump(self) -> str:
        lines = ["  Register File:"]
        qline = "    QR: " + " ".join(f"QR{i}=q{self.qregs[i]}" for i in range(NUM_QREGS))
        cline = "    CR: " + " ".join(f"CR{i}={self.cregs[i]}" for i in range(NUM_CREGS))
        return "\n".join([lines[0], qline, cline])


# ── 32-bit Instruction Encoding ───────────────────────────────────────────────
@dataclass
class Instruction:
    # Decoded fields
    opcode:   str
    itype:    str            # R / I / U / M / F / N(NOP)
    rd:       Optional[int] = None   # dest qubit reg
    rs1:      Optional[int] = None   # src qubit reg 1
    rs2:      Optional[int] = None   # src qubit reg 2
    crd:      Optional[int] = None   # dest classical reg
    crs:      Optional[int] = None   # src classical reg
    imm:      float          = 0.0   # rotation angle (I-type)
    pc:       int            = 0
    label:    str            = ""
    # Raw 32-bit encoding
    encoding: int            = 0

    def encode(self) -> int:
        """Pack instruction into 32-bit word (RISC-V style)."""
        op = MNEMONIC_TO_OPCODE.get(self.opcode, 0b1110011)
        word = op & 0x7F
        if self.itype == 'U':
            rd = (self.rd or 0) & 0x1F
            word |= (rd << 7)
        elif self.itype == 'R':
            rd  = (self.rd  or 0) & 0x1F
            rs1 = (self.rs1 or 0) & 0x1F
            word |= (rd << 7) | (rs1 << 15)
        elif self.itype == 'I':
            rd  = (self.rd or 0) & 0x1F
            # encode angle as fixed-point Q8.4 in imm[11:0]
            imm_enc = int(self.imm * 16) & 0xFFF
            word |= (rd << 7) | (imm_enc << 20)
        elif self.itype == 'M':
            qrd = (self.rd  or 0) & 0x1F
            crd = (self.crd or 0) & 0x1F
            word |= (qrd << 7) | (crd << 20)
        elif self.itype == 'F':
            qrd = (self.rd  or 0) & 0x1F
            crs = (self.crs or 0) & 0x1F
            word |= (qrd << 7) | (crs << 20)
        self.encoding = word
        return word

    def asm(self) -> str:
        """Return assembly-style string."""
        if self.itype == 'N':   return "NOP"
        if self.itype == 'U':   return f"{self.opcode:<8} QR{self.rd}"
        if self.itype == 'R':   return f"{self.opcode:<8} QR{self.rd}, QR{self.rs1}"
        if self.itype == 'I':   return f"{self.opcode:<8} QR{self.rd}, #{self.imm:.4f}"
        if self.itype == 'M':   return f"MEASURE  QR{self.rd} → CR{self.crd}"
        if self.itype == 'F':   return f"FEEDBACK QR{self.rd} ← CR{self.crs}"
        return self.opcode

    def __str__(self):
        return f"[PC={self.pc:02d}|0x{self.encode():08X}] {self.asm()}"


def make_nop(pc: int = 0) -> Instruction:
    i = Instruction(opcode='NOP', itype='N', pc=pc)
    i.encode()
    return i


# ── Assembler: list of dicts → Instruction objects ───────────────────────────
def assemble(prog: list) -> list:
    """
    Assemble a program written as dicts into Instruction objects with
    proper 32-bit encodings. Prints the ISA dump like a real assembler.
    """
    instructions = []
    print("\n  ┌─────────────────────────────────────────────────────────┐")
    print("  │           Q-RISC++ ASSEMBLER OUTPUT                     │")
    print("  ├────┬────────────────────┬────────────────┬──────────────┤")
    print("  │ PC │ Assembly           │ Encoding (hex) │ Type         │")
    print("  ├────┼────────────────────┼────────────────┼──────────────┤")
    for i, p in enumerate(prog):
        instr = Instruction(**p, pc=i)
        instr.encode()
        instructions.append(instr)
        itype_full = {'R':'R-type','I':'I-type','U':'U-type',
                      'M':'M-type','F':'F-type','N':'NOP'}[instr.itype]
        print(f"  │{i:3d} │ {instr.asm():<18} │ 0x{instr.encoding:08X}     │ {itype_full:<12} │")
    print("  └────┴────────────────────┴────────────────┴──────────────┘")
    return instructions
