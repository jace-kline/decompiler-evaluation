from lang import *
from lang_address import *
from lang_datatype import *

class Variable(object):
    def __init__(self, name=None, dtype=None, liveranges=None, param=False, function=None):
        """
        name: str
            The variable's name
        dtype: DataType
            The data type of the variable
        liveranges: [AddressLiveRange]
            The location this variable occupies throughout its lifetime.
            In unoptimized compilation, this usually will include only one address.
            However, live ranges and register splitting could be used in optimized compilation.
        param: bool
            Is this variable a parameter?
        function: Function | None
            The parent function, or None if global.
        """
        self.name = name
        self.dtype = dtype
        self.liveranges = sorted(liveranges) if bool(liveranges) else []
        self.param = param
        self.function = function

        if self.liveranges:
            self._verify_no_pc_overlaps()

    # No overlaps in PC ranges should be permitted
    def _verify_no_pc_overlaps(self):
        for i in range(0, len(self.liveranges) - 1):
            assert(self.liveranges[i].endpc <= self.liveranges[i + 1].startpc)

    def is_param(self):
        """ Is this variable a parameter? """
        return self.param

    def is_global(self):
        """ Is this variable a global variable? """
        return self.function is None

    def is_local(self):
        return not self.is_global() and not self.is_param()

    def has_location(self):
        return len(self.liveranges) > 0

    # is this variable linked to a single Varnode? i.e. a single live range?
    def is_single_loc(self):
        return len(self.liveranges) == 1

    def get_name(self):
        return self.name

    def get_datatype(self):
        return self.dtype

    def get_size(self):
        return self.get_datatype().get_size()

    # returns AddressLiveRangeSet
    def get_liveranges(self):
        return self.liveranges

    def get_parent_function(self):
        return self.function

    def get_liverange_at_pc(self, pc):
        for liverange in self.liveranges:
            if liverange.get_pc_range().contains(pc):
                return liverange
        return None

    # Given a PC Address, find the Address of the AddressLiveRange associated with the containing PC range (or None).
    def get_address_at_pc(self, pc):
        liverange = self.get_liverange_at_pc(pc)
        return liverange.get_addr() if liverange else None

    # for the given PC, find the Address where this Variable resides (or None).
    def get_address_at_pc(self, pc):
        if self.is_global():
            return self.liveranges[0].get_addr()
        
        for liverange in self.liveranges:
            if liverange.get_pc_range().contains(pc):
                return liverange.get_addr()

        return None

    # returns a list of Varnode objects corresponding to each of its
    # "instantiations"/liveranges.
    # () -> [Varnode]
    def get_varnodes(self):
        return [ Varnode(self.dtype, liverange, var=self) for liverange in self.liveranges ]

    def select_varnodes(self, varnode_cond=None):
        return [ varnode for varnode in self.get_varnodes() if varnode_cond is None or varnode_cond(varnode) ]

    def select_primitive_varnodes(self, varnode_cond=None):
        return sum([ varnode.select_primitive_varnodes(varnode_cond=varnode_cond) for varnode in self.get_varnodes() ], [])

    def __str__(self):
        lbl = "PARAM" if self.is_param() else "VAR"
        return "<{} {} :: {} @ {}>".format(lbl, self.name, self.dtype, self.liveranges)

    def __hash__(self):
        return hash((self.dtype, tuple(self.liveranges), self.param))

# the most atomic form of a variable-like entity
# a datatype, address, and pc range that indicates its lifetime
class Varnode(object):
    def __init__(self, dtype, liverange, var=None):
        self.dtype = dtype
        self.liverange = liverange
        self.var = var # the Variable that "spawned" this Varnode

    # () -> AddressLiveRange
    def get_liverange(self):
        return self.liverange

    # () -> Variable|None
    def get_var(self):
        return self.var

    # () -> AddressRange | None
    def get_pc_range(self):
        return self.liverange.get_pc_range()

    # () -> Address
    def get_addr(self):
        return self.liverange.get_addr()
        
    # () -> AddressRange
    def get_addr_range(self):
        return AddressRange(self.get_addr(), size=self.get_size())

    # () -> DataType
    def get_datatype(self):
        return self.dtype

    # () -> int
    def get_size(self):
        return self.get_datatype().get_size()

    # flattens this Varnode to Varnodes of only primitive datatypes
    # () -> [Varnode]
    def flatten(self):
        # [(offset: int, primtype: DataType)]
        dtype_flattened = self.dtype.flatten()

        varnodes = []
        for off, primtype in dtype_flattened:
            addr = self.get_addr().add_const(off)
            pc_range = self.get_pc_range()
            startpc = pc_range.get_start() if pc_range is not None else None
            endpc = pc_range.get_end() if pc_range is not None else None
            liverange = AddressLiveRange(addr=addr, startpc=startpc, endpc=endpc)
            varnodes.append(Varnode(primtype, liverange, var=self.var))

        return varnodes

    def select_primitive_varnodes(self, varnode_cond=None):
        return [ varnode for varnode in self.flatten() if varnode_cond is None or varnode_cond(varnode) ]
            

    # # builds a VarnodeCompareRecord|None from the infomation contained in the
    # # given variable. Only builds if the variable is associated with exactly one address.
    # @staticmethod
    # def from_single_location_variable(var: Variable) -> 'Union[Varnode, None]':
    #     liveranges = var.get_liveranges()
    #     return Varnode(var, liveranges[0].get_addr()) if liveranges and len(liveranges) == 1 else None

    # @staticmethod
    # def from_variable_at_pc(var: Variable, pc: AbsoluteAddress) -> 'Union[Varnode, None]':
    #     addr = var.get_address_at_pc(pc)
    #     return Varnode(var, addr) if addr is not None else None

    # @staticmethod
    # def from_unoptimized_variable(var: Variable) -> 'Union[Varnode, None]':
    #     varnode = Varnode.from_single_location_variable(var)
    #     return varnode if varnode is not None \
    #         else Varnode.from_variable_at_pc(var.get_datatype(), var.get_parent_function().get_start_pc())

    def __hash__(self):
        return hash((self.dtype, self.liverange))

    def __str__(self):
        return "<Varnode address={} datatype={}>".format(
            self.get_addr(),
            self.get_datatype()
        )

    def __repr__(self):
        return str(self)