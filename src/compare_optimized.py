from lang import *
from lang_address import *
from lang_datatype import *
from util import *

class StaticPCVariable(object):
    def __init__(self, pc, var):
        # self.var: Variable
        self.var = var

        # self.liverange: AddressLiveRange
        # holds the variable's address and associated PC range for the given PC
        self.liverange = self.var.get_liverange_at_pc(pc)

        # self.size: int
        self.size = None
        if self.liverange:
            self.size = self.var.get_datatype().get_size()
            self.size = self.size if self.size else 0
        
        # self.addr_range: AddressRange
        self.addr_range = None
        if self.liverange and self.size > 0 and AddressType.rangeable(self.get_addr().get_addrtype()):
            self.addr_range = AddressRange(self.get_addr(), size=self.size)

    # is this variable "alive" at the given PC? i.e., does it have a location?
    # This is assumed to be true for all other operations.
    def is_instantiated(self):
        return self.liverange is not None

    def get_var(self):
        return self.var

    def get_liverange(self):
        return self.liverange

    def get_pc_range(self):
        return self.liverange.get_pc_range()

    def get_addr(self):
        return self.liverange.get_addr()

    def get_size(self):
        return self.size

    def get_datatype(self):
        return self.var.get_datatype()

    def is_global(self):
        return self.var.is_global()

    def get_addrtype(self):
        return self.get_addr().get_addrtype()

    def get_addr_range(self):
        return self.addr_range

    # does this variable contain the given address?
    def contains(self, addr):
        if not self.is_instantiated():
            return False
        elif not self.addr_range:
            return addr == self.get_addr()
        else: # addr and addr_range are instantiated...
            self.addr_range.contains(addr)

    # if this Variable contains the given Address at this PC,
    # what is the offset from the start of this variable's range
    # to the addr? (always positive)
    # return None if this variable doesn't contain the given Address
    # Address -> int | None
    def contained_offset(self, addr):
        if self.contains(addr):
            return self.addr.distance(addr)
        return None

    # StaticPCVariable -> StaticPCVariableCompare2
    def compare(self, other):
        return StaticPCVariableCompare2(self, other)

    # codify uniqueness -> determined by parent variable (self.var) and the instantiated address (self.addr)
    def __hash__(self):
        return hash((self.var, self.addr))

    def __eq__(self, other):
        return self.var is other.var and self.addr == other.addr

class DataTypeCompare2(object):
    def __init__(self, left_dtype, right_dtype):
        self.left_dtype = left_dtype
        self.right_dtype = right_dtype

    def get_left_dtype(self):
        return self.left_dtype

    def get_right_dtype(self):
        return self.right_dtype

    def metatype_match(self):
        return self.left_dtype.get_metatype() == self.right_dtype.get_metatype()

    def size_match(self):
        return self.get_left_dtype.get_size() == self.get_right_dtype.get_size()

    def match(self):
        return self.get_left_dtype == self.get_right_dtype


# holds 2 StaticPCVariable objects + the AddressRangeOverlap between them + possibly datatype comparison
class StaticPCVariableCompare2(object):
    def __init__(self, left_var_inst, right_var_inst):
        self.left_var_inst = left_var_inst
        self.right_var_inst = right_var_inst
        self.addr_range_overlap = AddressRangeOverlap(
            self.left_var_inst.get_addr_range(),
            self.right_var_inst.get_addr_range()    
        )

        # the descent into the left var's type tree to find a match (or None)
        # should not be set if self.right_type_descent is set
        self.left_type_descent = None

        # the descent into the right var's type tree to find a match (or None)
        # should not be set if self.left_type_descent is set
        self.right_type_descent = None

        # A comparison of aligned datatypes / subtypes of the variables of the same size
        # Only set if there are datatypes at the same offset and of the same size
        # DataTypeCompare2 | None
        self.dtype_comparison = None

        # try to align / compare the datatypes of the 2 overlapping vars
        # this method will set the 3 members above
        self._compare_dtypes()   

    def _compare_dtypes(self):
        if self.does_overlap():
            # if right contains left, they could be equal or left is a subcomponent of right
            if self.addr_range_overlap.right_contains_left():
                # find the type (or component type) in the right var that matches
                # the offset and size of the left var
                self.right_type_descent = DataTypeRecursiveDescent.descend_find_type_at_offset_recursive(
                    self.right_var_inst.get_datatype(),
                    -1 * self.addr_range_overlap.start_distance(),
                    size=self.left_var_inst.get_size()
                )

            # if left contains right, the left dtype might be "over-inferenced"
            # we need to see if a subcomponent of the left matches the right
            elif self.addr_range_overlap.left_contains_right():
                # find the type (or component type) in the left var that matches
                # the offset and size of the right var
                self.left_type_descent = DataTypeRecursiveDescent.descend_find_type_at_offset_recursive(
                    self.left_var_inst.get_datatype(),
                    self.addr_range_overlap.start_distance(),
                    size=self.right_var_inst.get_size()
                )

        if self.right_type_descent is not None:
            self.dtype_comparison = DataTypeCompare2(self.left_var_inst.get_datatype(), self.right_type_descent.get_leaf())
        elif self.left_type_descent is not None:
            self.dtype_comparison = DataTypeCompare2(self.right_var_inst.get_datatype(), self.left_type_descent.get_leaf())

    def get_left_var_inst(self):
        return self.left_var_inst

    def get_right_var_inst(self):
        return self.right_var_inst

    def get_addr_range_overlap(self):
        return self.addr_range_overlap

    def does_overlap(self):
        return self.get_addr_range_overlap().does_overlap()

    def start_aligned(self):
        return self.get_addr_range_overlap().start_aligned()

    def size_equal(self):
        return self.left_var_inst.get_size() == self.right_var_inst.get_size()

    # did we have to "nest" into the subtypes of the left var type to match the right var type?
    def is_left_dtype_nested(self):
        return self.left_type_descent is not None and self.left_type_descent.get_depth() > 1

    # did we have to "nest" into the subtypes of the right var type to match the left var type?
    def is_right_dtype_nested(self):
        return self.right_type_descent is not None and self.right_type_descent.get_depth() > 1

    def get_dtype_comparison(self):
        return self.dtype_comparison

# Holds a StaticPCVariable + info pertaining to the comparison between this variable and another set of 
# StaticPCVariable objects.
# Tracks number of bytes "covered", variable overlaps, and more.
# Caches previous comparisons for fast lookup.
class StaticPCVariableCompareN(object):
    def __init__(self, var_inst):
        self.var_inst = var_inst

        # dict[id(StaticPCVariable), StaticPCVariableCompare2]
        self.comparisons = {}
        self.bytes_overlapped = 0

    # given a StaticPCVariable from another set, compare and update the internal state
    def add_comparison(self, other_var_inst):
        comparison = StaticPCVariableCompare2(self.var_inst, other_var_inst)
        if comparison.does_overlap():
            self.comparisons.append(comparison)
            self.bytes_overlapped += comparison.get_addr_range_overlap().bytes_overlapped()
        # TODO: finish

    def get_var_inst(self):
        return self.var_inst

    def get_comparisons(self):
        return self.comparisons

    def get_bytes_overlapped(self):
        return self.bytes_overlapped

    def get_comparison_var_insts(self):
        return [ cmp.get_overlap().get_right_var_inst() for cmp in self.comparisons ]

# represents a "snapshot" of an Address region at a given PC during program execution.
# holds a list of StaticPCVariable objects for the given region.
class StaticPCAddressSpace(object):
    def __init__(self, addrtype, var_insts):
        self.addrtype = addrtype
        self.var_insts = var_insts
        self._verify_var_inst_types()

    def _verify_var_inst_types(self):
        for var_inst in self.var_insts:
            assert (var_inst.get_addrtype() == self.addrtype)

    # is the given AddressSpace known / placeable in memory?
    # i.e., the address space is not UNKNOWN or EXTERNAL
    @staticmethod
    def is_known():
        return False

    # is the space rangeable?
    @staticmethod
    def is_rangeable():
        return False

    # does the space consist of only one location (e.g., a register)?
    @staticmethod
    def is_location():
        return False

    def get_addrtype(self):
        return self.addrtype

    def get_var_insts(self):
        return self.var_insts

    # is the other space referring to the same space as this one?
    # default behavior: simple comparison of addrtypes
    def same_space(self, other):
        return self.get_addrtype() == other.get_addrtype()

    # compares the variable instances of 2 address spaces
    # returns StaticPCAddressSpaceCompare2 | None
    def compare(self, other):
        raise NotImplementedError()

# Represents a snapshot of an Address space at a given PC.
# "Rangeable" address spaces include stack frames, heap regions, memory accessible as register offsets
class StaticPCAddressSpaceRangeable(StaticPCAddressSpace):
    def __init__(self, addrtype, var_insts):
        super(__class__, self).__init__(addrtype, var_insts)
        self.var_insts.sort(key=lambda v: v.addr)

    @staticmethod
    def is_known():
        return True

    @staticmethod
    def is_rangeable():
        return True

    def compare(self, other):
        assert( self.same_space(other) )
        #TODO: incorporate StaticPCVariableCompareRecord objects
        #TODO: use StaticPCAddressSpaceCompare2 to perform this logic
        
        # assume self & other var_insts are sorted ascending by addr
        # iterate over the 'Left', 'Right', and 'Conflict' objects
        zipper = OrderedZipper(
            self.var_insts,
            other.var_insts,
            key=lambda var_inst: var_inst.addr # sort by addr
        )

        # accumulate all StaticPCVariableCompare2 objects between left and right
        # variables in this address space
        comparisons = []

        # state variables
        # If prev_left set, then it implies that the prev_left addr range
        # could possibly overlap with the next right addr range.
        # The same applies for prev_right.

        # StaticPCVariable | None
        prev_left = None
        # StaticPCVariable | None
        prev_right = None

        for cur in zipper:
            if cur.is_left():
                left_var_inst = cur.get_value()
                if prev_right:
                    comparison = StaticPCVariableCompare2(left_var_inst, prev_right)
                    if comparison.does_overlap():
                        comparisons.append(comparison)
                    else:
                        prev_right = None
                prev_left = left_var_inst

            elif cur.is_right():
                right_var_inst = cur.get_value()
                if prev_left:
                    comparison = StaticPCVariableCompare2(prev_left, right_var_inst)
                    if comparison.does_overlap():
                        comparisons.append(comparison)
                    else:
                        prev_left = None
                prev_right = right_var_inst

            elif cur.is_conflict():
                left_var_inst, right_var_inst = cur.get_value()
                comparison = StaticPCVariableCompare2(left_var_inst, right_var_inst)
                if comparison.does_overlap():
                    comparisons.append(comparison)
                prev_left = left_var_inst
                prev_right = right_var_inst


# Represents an address "space" consisting of a single location
# Identified by its Address object
# e.g., a register location at a specific PC
class StaticPCAddressSpaceLocation(StaticPCAddressSpace):
    def __init__(self, var_inst):
        self.var_inst = var_inst
        super(__class__, self).__init__(self.get_addr().get_addrtype(), [var_inst])

    @staticmethod
    def is_known():
        return True

    @staticmethod
    def is_location():
        return True

    def get_addr(self):
        return self.var_inst.get_addr()

    def get_var_inst(self):
        return self.var_inst

    # is the other space referring to the same space as this one?
    # the locations must match exactly
    def same_space(self, other):
        return self.get_addr() == other.get_addr()

    def compare(self, other):
        # ensure the addresses being compared are identical
        assert( self.same_space(other) )

        return [StaticPCVariableCompare2(self.get_var_inst(), other.get_var_inst())]

# Represents a snapshot of an Address space at a given PC.
# Address spaces include stack frames, heap regions, memory accessible from register offset, register, etc.
class StaticPCAddressSpaceUnknown(StaticPCAddressSpace):
    def __init__(self, addrtype, var_insts):
        super(__class__, self).__init__(addrtype, var_insts)

    @staticmethod
    def is_known():
        return False

    # how to compare unknown locations?
    def compare(self, other):
        return []

class StaticPCAddressSpaceCompare2(object):
    def __init__(self, left_addrspace, right_addrspace):
        # ensure the left and right address spaces are pointing to the same region
        assert(left_addrspace.same_space(right_addrspace))
        self.left_addrspace = left_addrspace
        self.right_addrspace = right_addrspace
        
        self.var_inst_comparisons = self.left_addrspace.compare(self.right_addrspace)

    def get_left_addrspace(self):
        return self.left_addrspace

    def get_right_addrspace(self):
        return self.right_addrspace

    def get_var_inst_comparisons(self):
        return self.var_inst_comparisons

# the "context" of program variables at a given PC
class StaticPCContext(object):
    def __init__(self, pc, vars):
        self.pc = pc
        # map each Variable to a StaticPCVariable.
        # filter out the those that aren't "instantiated" at the given PC.
        self.var_insts = [ var_inst for var_inst 
            in ( StaticPCVariable(self.pc, var) for var in vars ) 
            if var_inst.is_instantiated() 
        ]

        # construct a list of StaticPCAddressSpace objects, one for each
        # address type present
        self.addrspaces = self._partition_addr_spaces()

    def _partition_addr_spaces(self):
        # collect each StaticPCVariable by AddressType
        # must separate registers by register number

        # keys: AddressType code (int)
        # values: [StaticPCVariable]
        _map = {}

        # keys: Register # (int)
        # values: StaticPCVariable
        _register_map = {}

        for var_inst in self.var_insts:
            addrtype = var_inst.get_addrtype()
            if addrtype == AddressType.REGISTER:
                regnum = var_inst.get_addr().get_register()
                _register_map[regnum] = var_inst
            elif addrtype in _map:
                _map[addrtype].append(var_inst)
            else:
                _map[addrtype] = [var_inst]

        # for each AddressType list of StaticPCVariables, construct
        # a StaticPCAddressSpace object
        # TODO: account for registers each having their own space
        # TODO: account for subclasses of StaticPCAddressSpace
        addrspaces = []
        for (addrtype, var_insts) in _map.items():
            space = StaticPCAddressSpaceRangeable(addrtype, var_insts) \
                if AddressType.rangeable(addrtype) \
                else StaticPCAddressSpaceUnknown(addrtype, var_insts)
            addrspaces.append(space)

        for (regnum, var_inst) in _register_map.items():
            addrspaces.append(StaticPCAddressSpaceLocation(var_inst))

        return addrspaces

    def get_addrspaces(self):
        return self.addrspaces

    # Address -> StaticPCVariable | None
    def get_var_inst_at_address(self, addr):
        for var_inst in self.var_insts:
            if var_inst.contains(addr):
                return var_inst
        return None

    # return StaticPCContextCompare2
    def compare(self, other):
        return StaticPCContextCompare2(self, other)

class StaticPCContextCompare2(object):
    def __init__(self, left_context, right_context):
        self.left_context = left_context
        self.right_context = right_context

        # TODO: 
        self.addrspace_comparisons = []

    def _merge_addrspaces(self):
        # we need addrspaces for each left and right to be in some order for easier merging
        # use OrderedZipper again?
        # define ordering based on AddressType of addrspaces?
        pass

    def _compare(self):
        pass
