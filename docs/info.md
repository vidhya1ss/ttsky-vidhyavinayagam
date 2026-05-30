<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works
The 7-bit ALU in Tiny Tapeout performs arithmetic and logical operations on two 7-bit inputs.
Based on the select signal, the ALU executes addition, subtraction, AND, or OR operations.
The design is implemented using combinational logic in Verilog HDL.
The ALU output is displayed through Tiny Tapeout output pins after synthesis and simulation.


## How to test

The 7-bit ALU can be tested using a Verilog testbench.
Different input values and select signals are applied to verify arithmetic and logical operations.
Simulation is performed using tools such as Icarus Verilog, GTKWave, or Vivado.
The output waveform confirms correct ALU functionality for all operations.


## External hardware

No external hardware components are used in this project.
The 7-bit ALU is fully implemented and tested using Tiny Tapeout ASIC design flow and Verilog simulation tools.
Input and output operations are verified through simulation waveforms.
The design is synthesized and validated using OpenLane/OpenROAD tools.

