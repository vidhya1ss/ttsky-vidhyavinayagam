# Makefile — RTL and gate-level simulation for tt_um_alu7b
# cocotb docs: https://docs.cocotb.org/en/stable/quickstart.html

# ── Defaults ──────────────────────────────────────────────────────────────────
SIM           ?= icarus
FST           ?= -fst
TOPLEVEL_LANG ?= verilog
SRC_DIR        = $(PWD)/../src

# ── Project sources — MUST match info.yaml:source_files ───────────────────────
PROJECT_SOURCES = alu_7b.v serial_alu_ctrl.v tt_um_alu7b.v

ifneq ($(GATES),yes)

# ── RTL simulation ────────────────────────────────────────────────────────────
SIM_BUILD        = sim_build/rtl
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))

else

# ── Gate-level simulation ─────────────────────────────────────────────────────
SIM_BUILD        = sim_build/gl
COMPILE_ARGS    += -DGL_TEST
COMPILE_ARGS    += -DFUNCTIONAL
COMPILE_ARGS    += -DUSE_POWER_PINS
COMPILE_ARGS    += -DSIM
COMPILE_ARGS    += -DUNIT_DELAY=\#1
VERILOG_SOURCES += $(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/verilog/primitives.v
VERILOG_SOURCES += $(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/verilog/sky130_fd_sc_hd.v
VERILOG_SOURCES += $(PWD)/gate_level_netlist.v

endif

# ── Allow shared includes from src/ ───────────────────────────────────────────
COMPILE_ARGS += -I$(SRC_DIR)

# ── Testbench ─────────────────────────────────────────────────────────────────
VERILOG_SOURCES += $(PWD)/tb.v
TOPLEVEL         = tb

# ── cocotb test module (no .py extension, comma-separated if multiple) ────────
COCOTB_TEST_MODULES = test

# ── Include cocotb build rules ────────────────────────────────────────────────
include $(shell cocotb-config --makefiles)/Makefile.sim
