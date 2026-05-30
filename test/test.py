# SPDX-FileCopyrightText: © 2026 Bootcamp IEEE OpenSilicon / IEEE CASS UTP
# SPDX-License-Identifier: Apache-2.0

"""
test.py — cocotb Testbench for tt_um_alu7b
===========================================

Module Under Test (DUT): tt_um_alu7b
  Instantiated as `user_project` in tb.v.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SERIAL PROTOCOL — tt_um_alu7b
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Rising edge  1 ..  7  → Operand A [6:0], LSB first  (bit_count 0..6)
  Rising edge  8 .. 14  → Operand B [6:0], LSB first  (bit_count 7..13)
  Rising edge 15        → S_CALC: reg_result ← alu_out, done_reg = 1 (1 cycle)

  Opcode: parallel input on ui_in[3:1] = op[2:0], stable throughout the
  operation. It does NOT need to be serialised through Bit_in.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OPERATION TABLE (reference: alu_7b.v)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  000 → ADD  result = {1'b0, A} + {1'b0, B}  [8 bits]  result[7] = carry-out
  001 → AND  result = {1'b0, A & B}                     result[7] = 0 (always)
  010 → OR   result = {1'b0, A | B}                     result[7] = 0 (always)
  011 → XOR  result = {1'b0, A ^ B}                     result[7] = 0 (always)
  100 → SUB  result = {1'b0, A} - {1'b0, B}  [8 bits]  result[7] = borrow (C2)

  Python expected values (A, B ∈ [0, 127]):
    ADD  expected = (A + B) & 0xFF
    SUB  expected = (A - B) & 0xFF   (8-bit two's complement)
    AND  expected = (A & B) & 0x7F   (result[7] always 0)
    OR   expected = (A | B) & 0x7F
    XOR  expected = (A ^ B) & 0x7F
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, FallingEdge

# ── Opcodes — must match alu_7b.v and tt_um_alu7b.v ──────────────────────────
OP_ADD = 0b000
OP_AND = 0b001
OP_OR  = 0b010
OP_XOR = 0b011
OP_SUB = 0b100

CLK_PERIOD_NS = 20   # 20 ns → 50 MHz (TinyTapeout digital I/O maximum)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: reset_dut
#
# Applies synchronous active-low reset to the DUT.
# rst_n = 0 takes effect on the next rising edge (synchronous reset in RTL).
# Held for 5 clock cycles for robust initialisation. Released on a falling
# edge so the caller's next action aligns with the DUT's first S_RECV cycle.
#
# Postcondition:
#   - FSM in S_RECV, bit_count = 0, reg_A = 0, reg_B = 0, reg_result = 0
#   - Control returned on a falling edge — next event is a rising edge
# ─────────────────────────────────────────────────────────────────────────────
async def reset_dut(dut):
    """Synchronous active-low reset. Returns on a falling edge."""
    dut.rst_n.value  = 0
    dut.ui_in.value  = 0
    dut.uio_in.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await FallingEdge(dut.clk)   # Align: next event will be a rising edge


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: run_alu
#
# Transmits 14 serial bits (7 for A, 7 for B), LSB first, and polls for Done.
#
# Precondition:
#   - DUT in S_RECV (after reset_dut), control on a falling edge
#
# Timing per bit:
#   bit[0]: present data → RisingEdge (no leading FallingEdge — already there)
#   bit[i > 0]: FallingEdge → present data → RisingEdge
#
# After 14 rising edges (bit_count reaches CNT_B_END = 13), FSM → S_CALC.
# On the 15th rising edge (S_CALC), result is latched and Done is asserted
# for exactly one cycle.
#
# Done is polled for up to 4 FallingEdge→RisingEdge pairs. Under normal
# conditions Done appears on the first iteration (15th rising edge total).
#
# Returns:
#   result (int): captured value of uo_out when Done was observed
#   done_seen (bool): True if Done was asserted within the polling window
# ─────────────────────────────────────────────────────────────────────────────
async def run_alu(dut, A, B, op):
    """
    Transmit 14 serial bits (A [6:0] + B [6:0], LSB first).
    Opcode is applied on ui_in[3:1] as a stable parallel input.
    Returns (result: int, done_seen: bool).
    """
    # Build the 14-bit serial sequence: A LSB-first then B LSB-first
    bits  = [(A >> i) & 1 for i in range(7)]
    bits += [(B >> i) & 1 for i in range(7)]

    for i, bit in enumerate(bits):
        if i > 0:
            await FallingEdge(dut.clk)   # Setup window (falling edge)
        # ui_in[0] = Bit_in, ui_in[3:1] = op[2:0], ui_in[7:4] = 0
        dut.ui_in.value = int(bit) | (op << 1)
        await RisingEdge(dut.clk)        # DUT captures on rising edge

    # Clear Bit_in but hold opcode stable (required during S_CALC)
    dut.ui_in.value = op << 1
    done_seen  = False
    result_val = 0

    # Poll for Done — up to 4 clock cycles
    for _ in range(4):
        await FallingEdge(dut.clk)
        await RisingEdge(dut.clk)
        if int(dut.uio_out.value) & 0x01:
            done_seen  = True
            result_val = int(dut.uo_out.value)
            break

    return result_val, done_seen


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TEST
# ─────────────────────────────────────────────────────────────────────────────
@cocotb.test()
async def test_project(dut):
    """
    Full verification of tt_um_alu7b — 20 test cases.

    Covers all 5 ALU operations (ADD, AND, OR, XOR, SUB) with both nominal
    and boundary scenarios aligned with the Bootcamp specification and the
    serial_tb.v Blocks A–F test set.

    Protocol: 14 serial bits (7 for A + 7 for B), opcode parallel on ui_in[3:1].
    """
    dut._log.info("=" * 65)
    dut._log.info("  tt_um_alu7b — Bootcamp IEEE OpenSilicon / IEEE CASS UTP 2026")
    dut._log.info("  Protocol: 14 serial bits (7A + 7B), opcode parallel ui_in[3:1]")
    dut._log.info("  Clock: %d ns (%d MHz)" % (CLK_PERIOD_NS, 1000 // CLK_PERIOD_NS))
    dut._log.info("=" * 65)

    # Start the clock
    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())

    # Robust initial reset
    dut.ena.value    = 1
    dut.ui_in.value  = 0
    dut.uio_in.value = 0
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await FallingEdge(dut.clk)

    dut._log.info("Initial reset complete. Starting test cases.")
    dut._log.info("-" * 65)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST CASE TABLE
    # Format: (A, B, op, expected, description)
    #
    # Expected values computed exactly as the RTL (alu_7b.v):
    #   ADD/SUB : 8-bit zero-extended arithmetic → & 0xFF
    #   AND/OR/XOR : 7-bit result, bit[7] forced 0  → & 0x7F
    # ─────────────────────────────────────────────────────────────────────────
    test_cases = [

        # ══════════════════════════════════════════════════════════════════════
        # BLOCK A — ADDITION (op = 000)
        # RTL reference: 3'b000: result = {1'b0, A} + {1'b0, B}
        # result[7] = carry-out (1 when A + B >= 128)
        # ══════════════════════════════════════════════════════════════════════
        (20,  30,  OP_ADD,
         (20  + 30)  & 0xFF,
         "ADD  20 +  30 =  50   [normal, no carry]"),

        (10,  15,  OP_ADD,
         (10  + 15)  & 0xFF,
         "ADD  10 +  15 =  25   [normal, no carry]"),

        (100, 100, OP_ADD,
         (100 + 100) & 0xFF,
         "ADD 100 + 100 = 0xC8  [carry, result[7]=1]"),

        (0,   0,   OP_ADD,
         0,
         "ADD   0 +   0 = 0x00  [zero case]"),

        (127, 1,   OP_ADD,
         (127 + 1)   & 0xFF,
         "ADD 127 +   1 = 0x80  [7-bit limit, carry]"),

        (127, 127, OP_ADD,
         (127 + 127) & 0xFF,
         "ADD 127 + 127 = 0xFE  [both max, carry]"),

        # ══════════════════════════════════════════════════════════════════════
        # BLOCK B — BITWISE AND (op = 001)
        # RTL reference: 3'b001: result = {1'b0, A & B}
        # result[7] = 0 always
        # ══════════════════════════════════════════════════════════════════════
        (0b1010101, 0b1100110, OP_AND,
         (0b1010101 & 0b1100110) & 0x7F,
         "AND 0x55 & 0x66 = 0x44 [partial mask]"),

        (0x7F, 0x00, OP_AND,
         0x00,
         "AND 0x7F & 0x00 = 0x00 [annihilation]"),

        (0x7F, 0x7F, OP_AND,
         0x7F,
         "AND 0x7F & 0x7F = 0x7F [identity]"),

        (0b0101010, 0b1010101, OP_AND,
         0x00,
         "AND 0x2A & 0x55 = 0x00 [crossed alternating, always 0]"),

        # ══════════════════════════════════════════════════════════════════════
        # BLOCK C — BITWISE OR (op = 010)
        # RTL reference: 3'b010: result = {1'b0, A | B}
        # result[7] = 0 always
        # ══════════════════════════════════════════════════════════════════════
        (0b0101010, 0b0010101, OP_OR,
         (0b0101010 | 0b0010101) & 0x7F,
         "OR  0x2A | 0x15 = 0x3F [complementary patterns]"),

        (0x00, 0x7F, OP_OR,
         0x7F,
         "OR  0x00 | 0x7F = 0x7F [OR identity]"),

        (0x7F, 0x7F, OP_OR,
         0x7F,
         "OR  0x7F | 0x7F = 0x7F [both operands at max]"),

        # ══════════════════════════════════════════════════════════════════════
        # BLOCK D — BITWISE XOR (op = 011)
        # RTL reference: 3'b011: result = {1'b0, A ^ B}
        # result[7] = 0 always
        # ══════════════════════════════════════════════════════════════════════
        (0b1111111, 0b1010101, OP_XOR,
         (0b1111111 ^ 0b1010101) & 0x7F,
         "XOR 0x7F ^ 0x55 = 0x2A [difference]"),

        (0b1100110, 0b1100110, OP_XOR,
         0x00,
         "XOR  A   ^  A   = 0x00 [self-cancellation]"),

        (0b1010101, 0b0101010, OP_XOR,
         (0b1010101 ^ 0b0101010) & 0x7F,
         "XOR 0x55 ^ 0x2A = 0x7F [alternating — all bits set]"),

        (0x7F, 0x00, OP_XOR,
         0x7F,
         "XOR 0x7F ^ 0x00 = 0x7F [XOR identity]"),

        # ══════════════════════════════════════════════════════════════════════
        # BLOCK E — SUBTRACTION (op = 100)
        # RTL reference: 3'b100: result = {1'b0, A} - {1'b0, B}
        # result[7] = borrow flag (1 when A < B; negative result in two's C)
        # ══════════════════════════════════════════════════════════════════════
        (50,  20,  OP_SUB,
         (50  - 20) & 0xFF,
         "SUB  50 -  20 =  30   [positive result, no borrow]"),

        (77,  77,  OP_SUB,
         0x00,
         "SUB  77 -  77 = 0x00  [A equals B — zero result]"),

        (10,  30,  OP_SUB,
         (10  - 30) & 0xFF,
         "SUB  10 -  30 = 0xEC  [underflow, borrow, two's complement]"),

        (127, 0,   OP_SUB,
         0x7F,
         "SUB 127 -   0 = 0x7F  [B = 0, no borrow]"),

    ]

    # ─────────────────────────────────────────────────────────────────────────
    # EXECUTION AND VERIFICATION LOOP
    # ─────────────────────────────────────────────────────────────────────────
    passed   = 0
    failed   = 0
    failures = []

    for idx, (A, B, op, expected, desc) in enumerate(test_cases):

        await reset_dut(dut)
        result, done = await run_alu(dut, A, B, op)

        ok     = (result == expected) and done
        status = "PASS" if ok else "FAIL"

        dut._log.info(
            "[%02d] %-52s  got=0x%02X  exp=0x%02X  Done=%d  [%s]"
            % (idx + 1, desc, result, expected, int(done), status)
        )

        if ok:
            passed += 1
        else:
            failed += 1
            failures.append((idx + 1, desc, result, expected, done))

    # ─────────────────────────────────────────────────────────────────────────
    # FINAL SUMMARY
    # ─────────────────────────────────────────────────────────────────────────
    dut._log.info("=" * 65)
    dut._log.info(
        "SUMMARY: %d PASS  /  %d FAIL  (total %d cases)"
        % (passed, failed, len(test_cases))
    )

    if failures:
        dut._log.error("FAILED CASES:")
        for num, desc, got, exp, d in failures:
            dut._log.error(
                "  [%02d] %s → got=0x%02X  exp=0x%02X  Done=%s  diff_bits=0x%02X"
                % (num, desc, got, exp, d, got ^ exp)
            )

    dut._log.info("=" * 65)

    # ─────────────────────────────────────────────────────────────────────────
    # INDIVIDUAL ASSERTIONS (reported by pytest in results.xml)
    # ─────────────────────────────────────────────────────────────────────────
    for num, desc, got, exp, d in failures:
        assert d, (
            "[%02d] %s: uio_out[0] (Done) was never asserted. "
            "Check: 14 bits transmitted, LSB-first protocol, "
            "FSM transition S_RECV → S_CALC at bit_count == CNT_B_END (13)."
            % (num, desc)
        )
        assert got == exp, (
            "[%02d] %s: incorrect result. "
            "got=0x%02X  expected=0x%02X  error_bits=0x%02X"
            % (num, desc, got, exp, got ^ exp)
        )
