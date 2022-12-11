## Common variable, function, and datatype representations for DWARF/Ghidra
from lang_address import *
from lang_datatype import *
from lang_variable import *

# hold the results of a translation into this common language
# from either DWARF info or Ghidra decompilation
class ProgramInfo(object):
    def __init__(self, globals=[], functions=[]):
        self.globals = globals
        self.functions = functions

    def get_globals(self):
        return self.globals

    def get_functions(self):
        return self.functions

    def select_globals(self, variable_cond=None):
        return [ var for var in self.globals if variable_cond is None or variable_cond(var) ]

    def select_functions(self, function_cond=None):
        return [ fn for fn in self.functions if function_cond is None or function_cond(fn) ]

    def select_variables(self, function_cond=None, variable_cond=None):
        return self.select_globals(variable_cond=variable_cond) + sum([ fn.select_variables(variable_cond=variable_cond) for fn in self.functions if function_cond is None or function_cond(fn) ], [])

    def select_varnodes(self, function_cond=None, variable_cond=None, varnode_cond=None):
        return sum([ gbl.select_varnodes(varnode_cond=varnode_cond) for gbl in self.globals if variable_cond is None or variable_cond(gbl) ], []) + sum([ fn.select_varnodes(variable_cond=variable_cond, varnode_cond=varnode_cond) for fn in self.functions if function_cond is None or function_cond(fn) ], [])

    def select_primitive_varnodes(self, function_cond=None, variable_cond=None, varnode_cond=None):
        return sum([ gbl.select_primitive_varnodes(varnode_cond=varnode_cond) for gbl in self.globals if variable_cond is None or variable_cond(gbl) ], []) + sum([fn.select_primitive_varnodes(variable_cond=variable_cond, varnode_cond=varnode_cond) for fn in self.functions if function_cond is None or function_cond(fn) ], [])

    def print_summary(self):
        print("----------------GLOBALS----------------------")
        for gbl in self.globals:
            print(gbl)


        print("----------------FUNCTIONS--------------------")
        for fn in self.functions:
            fn.print_summary()

    def __hash__(self):
        return hash((tuple(self.globals), tuple(self.functions)))

class Function(object):
    """
    Represents the debugging/decompilation information for a function.
    """
    def __init__(self, name=None, startaddr=None, endaddr=None, rettype=None, params=[], vars=[], variadic=False):
        """
        name: str
            The name of the function
        startaddr: Address
            The entrypoint address (global) of the function
        endaddr: Address
            The address of the last instruction in the function.
        proto: DataTypeFunctionPrototype
            The prototype of the function.
            Return type + parameter types.
        params: [Variable]
            A list of the function's parameters.
        vars: [Variable]
            A list of non-parameter variables declared and used within the body of the function.
        """
        self.name = name
        self.startaddr = startaddr
        self.endaddr = endaddr
        self.rettype = rettype
        self.params = params
        self.vars = vars
        self.variadic = variadic

    # if start and end addrs are None, this function is inlined
    # and doesn't occupy its own location in the binary
    def is_inlined(self):
        return self.startaddr is None and self.endaddr is None

    def is_variadic(self):
        return self.variadic

    def get_name(self):
        return self.name

    # returns DataTypeFunctionPrototype
    def get_prototype(self):
        return DataTypeFunctionPrototype(
            rettype=self.rettype,
            paramtypes=[ param.get_datatype() for param in self.params ],
            variadic=self.variadic
        )

    def get_return_type(self):
        return self.rettype

    def get_pc_range(self):
        return AddressRange(self.startaddr, end=self.endaddr)

    def get_start_pc(self):
        return self.startaddr

    def get_end_pc(self):
        return self.endaddr

    def get_params(self):
        return self.params

    def get_vars(self):
        return self.vars

    def same(self, other):
        return self.startaddr == other.startaddr

    def select_params(self, variable_cond=None):
        return [ var for var in self.params if variable_cond is None or variable_cond(var) ]

    def select_locals(self, variable_cond=None):
        return [ var for var in self.vars if variable_cond is None or variable_cond(var) ]

    def select_variables(self, variable_cond=None):
        return self.select_params(variable_cond=variable_cond) + self.select_locals(variable_cond=variable_cond)

    def select_varnodes(self, variable_cond=None, varnode_cond=None):
        return sum([ var.select_varnodes(varnode_cond=varnode_cond) for var in self.select_variables(variable_cond=variable_cond) ], [])

    def select_primitive_varnodes(self, variable_cond=None, varnode_cond=None):
        return sum([ var.select_primitive_varnodes(varnode_cond=varnode_cond) for var in self.select_variables(variable_cond=variable_cond) ], [])

    def print_summary(self):
        print("{} :: {} @ PC range=({}, {})".format(self.name, self.get_prototype(), self.startaddr, self.endaddr))
        for var in (self.params + self.vars):
            print("\t{}".format(var))

    def __hash__(self):
        return hash((self.startaddr, self.endaddr, self.rettype, tuple(self.params), tuple(self.vars), self.variadic))
