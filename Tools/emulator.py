#!/usr/bin/env python3

from enum import Enum
import tkinter as tk
from tkinter import scrolledtext
from tkinter import filedialog

import helpers
import assembler


# ~~~~~~~~ Begin Hardware Definition ~~~~~~~~
# A class to implement a simple register
class Register:
    def __init__(self, bits):
        self.bits = bits
        
        self.value = None
        
        # Set status
        self.set_flag = False
    
    
    def set(self, value):
        # Overflow inputs if needed
        value %= 2 ** self.bits
        
        self.value = value
        
        if not self.set_flag:
            self.set_flag = True
    
    
    def is_set(self):
        return self.set_flag
    
    
    def get(self):
        if not self.is_set():
            raise Exception("The register has not been set yet, no value to get!")
        
        return self.value



# A class to implement an ALU object, with flags and an accumulator
class ALU:
    def __init__(self, bits):
        # Bit width
        self.bits = bits
        
        # Flag bits out
        self.cout = None
        self.eqz = None
        self.nez = None
        self.ltz = None
        self.gtz = None
        self.lez = None
        self.gez = None
        
        # Accumulator
        self.acc = Register(self.bits)
        
        # Unset status
        self.unset = True
    
    
    # A class to implement the ALU operations
    class Instruction(Enum):
        ADD = 0
        NAND = 1
    
    
    def invert(self, X):
        # Overflow inputs if needed
        X %= 2 ** self.bits
        
        # Get binary string
        binstring = "{0:b}".format(X)
        
        # Invert each bit
        out = ""
        for bit in binstring:
            if bit == "0":
                out += "1"
            else:
                out += "0"
        
        # Pad with 1's to fill the zeros that were missing at the start
        out = out.rjust(self.bits, "1")
        
        # Convert back to an integer
        out = int(out, 2)
        
        return out
    
    
    def add(self, A, B, cin):
        # Overflow inputs if needed
        A %= 2 ** self.bits
        B %= 2 ** self.bits
        
        # Take the sum
        sum = A + B
        
        # Add the carry in
        if cin:
            sum += 1
        
        # Test if we have a carry out
        if sum >= 2 ** self.bits:
            cout = True
        else:
            cout = False
        
        # Overflow the output
        sum %= 2 ** self.bits
        
        return sum, cout
    
    
    def calc(self, f, X, Y, cin=False):
        # Overflow inputs if needed
        X %= 2 ** self.bits
        Y %= 2 ** self.bits
        
        
        # Convert `f` to bool if needed
        if type(f) is not bool:
            command = f
            if command == self.Instruction.ADD:
                f = True
            elif command == self.Instruction.NAND:
                f = False
            else:
                raise Exception("\"{}\" is not a valid ALU command!".format(command))
        
        # Add to get the carry no matter what
        sum, cout = self.add(X, Y, cin)
        
        # Select output
        if f:
            # Add
            out = sum
        else:
            # NAND
            out = self.invert(X & Y)
        
        # Set flags
        self.cout = cout
        
        self.eqz = (out == 0)
        self.nez = (not self.eqz)
        
        self.ltz = (out >= (2** (self.bits - 1) ))
        self.gez = (not self.ltz)
        
        
        self.lez = (self.ltz or self.eqz)
        self.gtz = (not self.lez)
        
        if self.unset:
            self.unset = False
        
        # Set accumulator
        self.acc.set(out)
    
    
    def bit_width(self):
        return self.bits
    
    
    def flags(self):
        if self.unset:
            raise Exception("ALU has not had any calculations run yet, no flags available!")
        return {"cout" : self.cout,
                "eqz"  : self.eqz,
                "nez"  : self.nez,
                "ltz"  : self.ltz,
                "gtz"  : self.gtz,
                "lez"  : self.lez,
                "gez"  : self.gez}
    
    
    def get_ACC(self):
        return self.acc.get()



# A class to implement a RAM, with an internal MAR
class RAM:
    def __init__(self, data_bits, address_bits):
        self.data_bits = data_bits
        self.address_bits = address_bits
        
        self.words = 2**self.address_bits
        self.registers = [Register(self.data_bits) for _ in range(self.words)]
        
        self.address = Register(self.address_bits)
    
    def set_address(self, address):
        # Overflow inputs if needed
        address %= 2 ** self.address_bits
        
        self.address.set(address)
        
        
    def write(self, value):
        # Overflow inputs if needed
        value %= 2 ** self.data_bits
        
        self.registers[self.address.get()].set(value)
    
    def read(self):
        return self.registers[self.address.get()].get()



# A class to implement the program ROM, with an integrated program counter register
class ProgramROM:
    def __init__(self, data_bits, address_bits):
        self.data_bits = data_bits
        self.address_bits = address_bits
        
        self.words = 2**self.address_bits
        self.clear()
        
        self.pc = Register(self.address_bits)
        self.pc.set(0)
        
        self.asm = None
    
    
    # Clear ROM
    def clear(self):
        self.instructions = [None for _ in range(self.words)]
    
    
    # Parse a text file into instructions
    def program(self, file_in):
        # Erase
        self.clear()
        
        # Make assembler for file
        self.asm = assembler.Assembler(file_in)
        
        # Run assembly
        self.asm.run()
        
        # Program commands into ROM
        for instruction in self.asm.assembled_objects():
            self.instructions[instruction["address"]] = instruction
    
    
    def set_address(self, address):
        # Overflow inputs if needed
        address %= 2 ** self.address_bits
        
        self.pc.set(address)
    
    
    def increment(self):
        self.set_address(self.pc.get() + 1)
    
    
    def read(self):
        return self.instructions[self.pc.get()]
    
    
    def address(self):
        return self.pc.get()
    
    
    # Return the processed assembly in it's human-readable symbolic form
    def processed_assembly(self):
        return self.asm.processed_assembly()
    
    
    # Return the current instruction in human readable form
    def instruction_asm(self):
        return self.processed_assembly()[self.pc.get()]



# A class to represent the complete FET-80 hardware system
class Fet80:
    def __init__(self):
        # Set bit widths
        self.data_bits = assembler.Fet80Params.DataWidth
        self.address_bits = assembler.Fet80Params.AddressWidth

        # Make an ALU
        self.alu = ALU(self.data_bits)

        # Make the registers
        self.registers = { "A" : Register(self.data_bits),
                           "B" : Register(self.data_bits) }
        
        # Make the RAM
        self.ram = RAM(data_bits=self.data_bits, address_bits=self.address_bits)

        # Make the ROM
        self.rom = ProgramROM(data_bits=self.data_bits, address_bits=self.address_bits)
    
    
    #  A function to program the ROM with an assembly file
    def program(self, file_in):
        self.rom.program(file_in)
        self.rom.program(file_in)
    
    
    # A helper function to get the bit widths used in the system
    def bits(self):
        return { "data"    : self.data_bits,
                 "address" : self.address_bits }
    
    
    # Sets the A register data
    def set_A(self, value):
        self.registers["A"].set(value)
        
    
    # Reads the A register data
    def get_A(self):
        return self.registers["A"].get()
    
    
    # Sets the B register data
    def set_B(self, value):
        self.registers["B"].set(value)
        
    
    # Reads the B register data
    def get_B(self):
        return self.registers["B"].get()
    
    
    # Sets the RAM address
    def set_M_address(self, value):
        self.ram.set_address(value)
    
    
    # Sets the RAM data (register M)
    def set_M(self, value):
        self.ram.write(value)
    
    
    # Reads the RAM data (register M)
    def get_M(self):
        return self.ram.read()
    
    
    # Sets the program counter (ROM address) for J instructions
    def set_PC(self, value):
        self.rom.set_address(value)
    
    
    # Reads the PC
    def get_PC(self):
        return self.rom.address()
    
    
    # Increments the program counter
    def increment_PC(self):
        self.rom.increment()
    
    
    # Reads the current instruction from ROM
    def instruction(self):
        return self.rom.read()
    
    
    # Uses the ALU to compute a NAND operation
    def nand(self, x, y):
        self.alu.calc( f   = False,
                       X   = x,
                       Y   = y,
                       cin = False )
    
    
    # Uses the ALU to compute an ADD operation
    def add(self, x, y, cin=False):
        self.alu.calc( f   = True,
                       X   = x,
                       Y   = y,
                       cin = cin )
    
    
    # Reads the accumulator from the ALU
    def get_ACC(self):
        return self.alu.get_ACC()
    
    
    # Reads the flags from the ALU
    def flags(self):
        return self.alu.flags()
    
    
    # Returns the RAM register array
    def get_RAM(self):
        return self.ram.registers
    
    
    # Return the processed assembly in it's human-readable symbolic form
    def processed_assembly(self):
        return self.rom.processed_assembly()
    
    
    # Return the current instruction in human readable form
    def instruction_asm(self):
        return self.processed_assembly()[self.get_PC()]
# ~~~~~~~~ End Hardware Definition ~~~~~~~~


# ~~~~~~~~ Begin Emulator Definition ~~~~~~~~
# The main emulator class
class Emulator:
    def __init__(self):
        # Make the FET-80 hardware system
        self.fet80 = Fet80()
        
        # Make current program string variable
        self.current_program = None
        
        # Make helpful decimal converters for printing and such
        self.dec_data = helpers.Dec2(self.fet80.bits()["data"])
        self.dec_address = helpers.Dec2(self.fet80.bits()["address"])
    
    
    # load a program
    def load_program(self, file_in):
        self.current_program = file_in
        self.fet80.program(self.current_program)
    
    
    # Returns the source code text of the current program
    def source_code(self):
        if self.current_program is None:
            raise Exception("No program has been loaded into the emulator yet!")
        with open(self.current_program, "r") as f:
            result = f.read()
        return result
    
    
    # Get the current instruction
    def instruction(self):
        return self.fet80.instruction()
    
    
    # Read the A register
    def get_A(self):
        return self.fet80.get_A()
    
    
    # Read the B register
    def get_B(self):
        return self.fet80.get_B()
    
    
    # Read the current memory value
    def get_M(self):
        return self.fet80.get_M()
    
    
    # Read the current memory address
    def get_M_address(self):
        return self.fet80.get_M_address()
    
    
    # Read the PC
    def get_PC(self):
        return self.fet80.get_PC()
    
    
    # Read the ACC
    def get_ACC(self):
        return self.fet80.get_ACC()
    
    
    # Reads the flags from the ALU
    def flags(self):
        return self.fet80.flags()
    
    
    # A helper function to get the source value from an instruction (register or direct)
    def get_source_value(self, instruction):
        if instruction["src"] == assembler.AsmCodes.Src.DV:
            # A direct value for `src`
            value = instruction["value"]
        elif instruction["src"] == assembler.AsmCodes.Src.A:
            # A register is `src`
            value = self.get_A()
        elif instruction["src"] == assembler.AsmCodes.Src.B:
            # B register is `src`
            value = self.get_B()
        elif instruction["src"] == assembler.AsmCodes.Src.M:
            # RAM is `src`
            value = self.get_M()
        else:
            raise Exception("Invalid source! (address: {})".format(instruction["address"]))
        return value
    
    
    # A helper function to get the destination value from an instruction (register)
    def get_destination_value(self, instruction):
        if instruction["dest"] == assembler.AsmCodes.Dest.A:
            # A register is `dest`
            value = self.get_A()
        elif instruction["dest"] == assembler.AsmCodes.Dest.B:
            # B register is `dest`
            value = self.get_B()
        elif instruction["dest"] == assembler.AsmCodes.Dest.M:
            # RAM is `dest`
            value = self.get_M()
        else:
            raise Exception("Invalid destination! (address: {})".format(instruction["address"]))
        return value
    
    
    # A helper function to set a destination in an instruction to a value
    def set_destination_value(self, instruction, value):
        if instruction["dest"] == assembler.AsmCodes.Dest.A:
            # A register is `dest`
            self.fet80.set_A(value)
        elif instruction["dest"] == assembler.AsmCodes.Dest.B:
            # B register is `dest`
            self.fet80.set_B(value)
        elif instruction["dest"] == assembler.AsmCodes.Dest.M:
            # RAM is `dest`
            self.fet80.set_M(value)
        else:
            raise Exception("Invalid destination! (address: {})".format(instruction["address"]))
    
    
    # Perform a T-instruction
    def run_T(self, instruction):
        # A `MOV` instruction, move `src` to `dest`
        value = self.get_source_value(instruction)
        self.set_destination_value(instruction, value)
        
        self.fet80.increment_PC()
    
    
    # Perform an M-instruction
    def run_M(self, instruction):
        # A `MEM` instruction, to move `src` to the MAR
        value = self.get_source_value(instruction)
        self.fet80.set_M_address(value)
        
        self.fet80.increment_PC()
    
    
    # Perform a C-instruction
    def run_C(self, instruction):
        # Either an `ADD` or `NAND` instruction
        # Run the operands through the ALU
        # Then, move the accumulator to `dest`
        X = self.get_destination_value(instruction)
        Y = self.get_source_value(instruction)
        if instruction["opcode"] == assembler.AsmCodes.Opcode.ADD:
            self.fet80.add(x=X, y=Y)
        elif instruction["opcode"] == assembler.AsmCodes.Opcode.NAND:
            self.fet80.nand(x=X, y=Y)
        else:
            raise Exception("Invalid opcode for a C instruction! (address: {})".format(instruction["address"]))
        self.set_destination_value(instruction, self.get_ACC())
        
        self.fet80.increment_PC()
    
    
    # Perform a J-instruction
    def run_J(self, instruction):
        # A jump instruction of some type
        # First, we check the state of the ALU flags to see if we need to jump
        # If we need to jump, move the src to the PC
        # Otherwise, and ONLY otherwise, do we increment PC
        if instruction["opcode"] == assembler.AsmCodes.Opcode.JMP:
            # Always
            jump = True
        elif instruction["opcode"] == assembler.AsmCodes.Opcode.JC:
            jump = self.flags()["cout"]
        elif instruction["opcode"] == assembler.AsmCodes.Opcode.JNC:
            jump = not self.flags()["cout"]
        elif instruction["opcode"] == assembler.AsmCodes.Opcode.JEQZ:
            jump = self.flags()["eqz"]
        elif instruction["opcode"] == assembler.AsmCodes.Opcode.JNEZ:
            jump = self.flags()["nez"]
        elif instruction["opcode"] == assembler.AsmCodes.Opcode.JGTZ:
            jump = self.flags()["gtz"]
        elif instruction["opcode"] == assembler.AsmCodes.Opcode.JLTZ:
            jump = self.flags()["ltz"]
        elif instruction["opcode"] == assembler.AsmCodes.Opcode.JGEZ:
            jump = self.flags()["gez"]
        elif instruction["opcode"] == assembler.AsmCodes.Opcode.JLEZ:
            jump = self.flags()["lez"]
        else:
            raise Exception("Invalid opcode for a J instruction! (address: {})".format(instruction["address"]))
        
        if jump:
            address = self.get_source_value(instruction)
            self.fet80.set_PC(address)
        else:
            self.fet80.increment_PC()
    
    
    # Perform a D-instruction
    def run_D(self, instruction):
        # `NOP`, do nothing
        return
    
    
    # Run a single full instruction cycle
    def step(self):
        # First, we run the actual command
        # Each command updates the PC accordingly
        instruction = self.instruction()
        if instruction["type"] == assembler.AsmCodes.InstructionType.T_INSTRUCTION:
            self.run_T(instruction)
        elif instruction["type"] == assembler.AsmCodes.InstructionType.M_INSTRUCTION:
            self.run_M(instruction)
        elif instruction["type"] == assembler.AsmCodes.InstructionType.C_INSTRUCTION:
            self.run_C(instruction)
        elif instruction["type"] == assembler.AsmCodes.InstructionType.J_INSTRUCTION:
            self.run_J(instruction)
        elif instruction["type"] == assembler.AsmCodes.InstructionType.D_INSTRUCTION:
            self.run_D(instruction)
        else:
            raise Exception("Invalid instruction type! (address: {})".format(instruction["address"]))
    
    
    # Returns the RAM register array
    def get_RAM(self):
        return self.fet80.get_RAM()
    
    
    # Returns the RAM as an integer array
    def get_RAM_int(self, unset=None):
        out = list()
        for r in self.get_RAM():
            if r.is_set():
                out.append(r.get())
            else:
                out.append(unset)
        
        return out
    
    
    # Return the processed assembly in it's human-readable symbolic form
    def processed_assembly(self):
        return self.fet80.processed_assembly()
    
    
    # Return the current instruction in human readable form
    def instruction_asm(self):
        return self.processed_assembly()[self.get_PC()]
# ~~~~~~~~ End Emulator Definition ~~~~~~~~


# ~~~~~~~~ Begin GUI Definition ~~~~~~~~
# The main window
class MainWindow:
    def __init__(self):
        self.root = None
        self.emu = Emulator()
        self.padding = 6
    
    
    # Load a program into the emulator
    def load_program(self, file_in):
        self.emu.load_program(file_in)
        # Update the UI
        self.set_textbox_text_numbered(self.source_text, self.source_code(), line_start=1)
    
    
    # Get the current program source code
    def source_code(self):
        return self.emu.source_code()
    
    
    # Open the GUI to load a file
    def load_file_gui(self):
        filetypes  = ( ("FET-80 assembly files", "*.f80asm" ),
                       ("All files"     , "*.*") )
        filename = filedialog.askopenfilename( title      = "Open a FET-80 Assembly File...",
                                               initialdir = ".",
                                               filetypes  = filetypes )
        self.load_program(filename)  
    
    
    # Returns the frame of the navbar
    def make_navbar(self):
        self.navbar = tk.Button( self.root, 
                                 text = "Load File...",
                                 bd = 2,
                                 command = self.load_file_gui )
        return self.navbar
    
    
    # Returns the frame of the source code area
    def make_source_area(self):
        self.source_text = scrolledtext.ScrolledText( self.root, 
                                                      wrap   = tk.NONE, 
                                                      width  = 45, 
                                                      height = 35, 
                                                      font   = ("Courier New", 10),
                                                      state  = tk.DISABLED )
        return self.source_text
    
    
    # Sets the a textbox's text
    def set_textbox_text(self, text_object, text_in):
        text_object.configure(state="normal")
        text_object.delete(1.0, "end")
        text_object.insert(1.0, text_in)
        text_object.configure(state="disabled")
    
    
    # Sets the a textbox's text with numbered lines
    def set_textbox_text_numbered(self, text_object, text_in, line_start=0, delimiter=". "):
        text_lines = text_in.splitlines()
        # Get the biggest number length
        number_length = len(str(len(text_lines)))
        text_processed = ""
        for i, line in enumerate(text_lines):
            new_line = str(line_start+i)
            new_line = new_line.rjust(number_length)
            new_line += delimiter + line + "\n"
            text_processed += new_line
        
        self.set_textbox_text(text_object, text_processed)
    
    
    # Returns the frame of the program code area
    def make_code_area(self):
        return tk.Label(self.root, text="I'll be program code one day.", font="helvetica 12")
    
    
    # Returns the frame of the RAM area
    def make_RAM_area(self):
        return tk.Label(self.root, text="I'll be RAM contents one day.", font="helvetica 12")
    
    
    # Returns the frame of the screen area
    def make_screen_area(self):
        return tk.Label(self.root, text="I'll be the screen one day.", font="helvetica 12")
    
    
    # Returns the frame of the info area
    def make_info_area(self):
        return tk.Label(self.root, text="I'll be status info one day.", font="helvetica 12")
    
    
    # Main call
    def run(self):
        # Make window
        self.root = tk.Tk()
        
        # Make navbar area
        self.navbar = self.make_navbar()
        self.navbar.grid(row=0, column=0, columnspan=3, padx=self.padding, pady=self.padding)
        
        # Make source text area
        self.source_area = self.make_source_area()
        self.source_area.grid(row=1, column=0, rowspan=2, padx=self.padding, pady=self.padding)
        
        # Make program code area
        self.code_area = self.make_code_area()
        self.code_area.grid(row=2, column=1, padx=self.padding, pady=self.padding)
        
        # Make RAM area
        self.memory_area = self.make_RAM_area()
        self.memory_area.grid(row=1, column=1, padx=self.padding, pady=self.padding)
        
        # Make screen area
        self.screen_area = self.make_screen_area()
        self.screen_area.grid(row=1, column=2, padx=self.padding, pady=self.padding)
        
        # Make info area
        self.info_area = self.make_info_area()
        self.info_area.grid(row=2, column=2, padx=self.padding, pady=self.padding)
        
        # Start main event loop
        self.root.mainloop()
# ~~~~~~~~ End GUI Definition ~~~~~~~~


# ~~~~~~~~ Begin Main Program ~~~~~~~~
# Make the main window
main_window = MainWindow()

# Run the main window loop
main_window.run()

# Load the test code #TODO remove
#main_window.load_program("../Code/XOR.f80asm")  

'''
def main():
    return 0
    
if __name__ == '__main__':
    # Run main
    exit_code = main()
    sys.exit(exit_code)
'''