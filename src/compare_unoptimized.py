from symbol import comparison
from typing import List, Tuple, Union
from collections import OrderedDict

from lang import *
from lang_address import *
from lang_datatype import *
from lang_variable import *
from util import *

from compare_variable import *
from compare_scope import *

class UnoptimizedProgramInfo(object):
    def __init__(self, proginfo: ProgramInfo):
        self.proginfo: ProgramInfo = proginfo
        
        # maps function start address to UnoptimizedFunction object
        self.unoptimized_functions: OrderedDict[AbsoluteAddress, UnoptimizedFunction] \
            = self._make_unoptimized_functions()

        # the set of global variables (converted to Varnodes)
        self.globals: List[Varnode] = self._make_unoptimized_globals()

        # re-expose SELECT functions
        self.select_functions = self.proginfo.select_functions
        self.select_variables = self.proginfo.select_variables
        self.select_varnodes = self.proginfo.select_varnodes
        self.select_primitive_varnodes = self.proginfo.select_primitive_varnodes

    def _make_unoptimized_functions(self) -> 'OrderedDict[AbsoluteAddress, UnoptimizedFunction]':
        _map = {}
        for function in self.get_proginfo().get_functions():
            _map[function.get_start_pc()] = UnoptimizedFunction(function)

        # sort the dict by key (Address) & return
        return ordered_dict_by_key(_map)

    def _make_unoptimized_globals(self) -> List[Varnode]:
        # varnodes = [ 
        #     varnode for varnode in 
        #     [ Varnode.from_single_location_variable(var) for var in self.proginfo.get_globals() ]
        #     if varnode is not None
        # ]
        varnodes = []
        for var in self.get_proginfo().get_globals():
            vnodes = var.get_varnodes()
            if(len(vnodes) == 1):
                varnodes.append(vnodes[0])
        
        return varnodes

    def get_proginfo(self) -> ProgramInfo:
        return self.proginfo

    def get_unoptimized_functions(self) -> 'OrderedDict[AbsoluteAddress, UnoptimizedFunction]':
        return self.unoptimized_functions

    def get_unoptimized_globals(self) -> List[Varnode]:
        return self.globals

    def __hash__(self) -> int:
        return hash(self.proginfo)

class UnoptimizedProgramInfoCompare2(object):
    def __init__(self,
        left: UnoptimizedProgramInfo,
        right: UnoptimizedProgramInfo
    ):
        self.left = left
        self.right = right

        # compare global variable sets
        self.globals_comparison = ConstPCVariableSetSnapshotCompare2(
            ConstPCVariableSetSnapshot(self.left.get_unoptimized_globals()),
            ConstPCVariableSetSnapshot(self.right.get_unoptimized_globals())
        )

        # store dict of UnoptimizedFunction -> UnoptimizedFunctionCompareRecord
        self.unoptimized_function_compare_map = self._make_function_compare_map()

        # re-expose function SELECT methods for left proginfo
        self.select_left_functions = self.left.select_functions
        self.select_left_variables = self.left.select_variables
        self.select_left_varnodes = self.left.select_varnodes
        self.select_left_primitive_varnodes = self.left.select_primitive_varnodes

        # re-expose function SELECT methods for right proginfo
        self.select_right_functions = self.right.select_functions
        self.select_right_variables = self.right.select_variables
        self.select_right_varnodes = self.right.select_varnodes
        self.select_right_primitive_varnodes = self.right.select_primitive_varnodes

    # map unoptimized functions to compare records
    # order the map by the start PC of the function
    def _make_function_compare_map(self) -> 'OrderedDict[UnoptimizedFunction, UnoptimizedFunctionCompareRecord]':
        key = lambda fn: fn.get_start_pc()

        # use Zipper util to find conflicts based on start PC
        # assume ordered unoptimized functions based on start PC from both sets
        zipper = OrderedZipper(
            self.left.get_unoptimized_functions().values(),
            self.right.get_unoptimized_functions().values(),
            key=key # order by start PC
        )
        
        _map = {}

        for cur in zipper:
            # if left only, map function->None
            if cur.is_left():
                l = cur.get_value()
                _map[l] = UnoptimizedFunctionCompareRecord(l, None)
            
            # if matching start PC, map function->comparison
            elif cur.is_conflict():
                l, r = cur.get_value()
                comparison = UnoptimizedFunctionCompare2(l, r)
                _map[l] = UnoptimizedFunctionCompareRecord(l, comparison)

        return ordered_dict_by_key(_map, transform=key)


    def get_left(self) -> UnoptimizedProgramInfo:
        return self.left

    def get_right(self) -> UnoptimizedProgramInfo:
        return self.right

    def get_function_compare_record(self, unoptimized_fn: 'UnoptimizedFunction') -> 'Union[UnoptimizedFunctionCompareRecord, None]':
        return self.unoptimized_function_compare_map.get(unoptimized_fn, None)

    def get_function_compare_record_map(self) -> 'dict[UnoptimizedFunction, UnoptimizedFunctionCompareRecord]':
        return self.unoptimized_function_compare_map

    def get_function_compare_records(self) -> List['UnoptimizedFunctionCompareRecord']:
        return self.unoptimized_function_compare_map.values()

    def get_varnode_compare_records(self) -> List[VarnodeCompareRecord]:
        gbl_records = self.globals_comparison.get_varnode_compare_records()
        fn_varnode_records = sum( [ fn_cmp.get_varnode_compare_records() for fn_cmp in self.get_function_compare_records() ], [])
        return gbl_records + fn_varnode_records

    def get_primitive_varnode_compare_records(self) -> List[VarnodeCompareRecord]:
        gbl_records = self.globals_comparison.get_flattened_comparison().get_varnode_compare_records()
        fn_varnode_records = sum( [ fn_cmp.get_primitive_varnode_compare_records() for fn_cmp in self.get_function_compare_records() ], [])
        return gbl_records + fn_varnode_records

    def get_globals_comparison(self) -> ConstPCVariableSetSnapshotCompare2:
        return self.globals_comparison

    def get_primitive_globals_comparison(self) -> ConstPCVariableSetSnapshotCompare2:
        return self.globals_comparison.get_flattened_comparison()

    def get_global_compare_record(self, global_varnode: Varnode) -> 'Union[VarnodeCompareRecord, None]':
        return self.globals_comparison.get_varnode_compare_record(global_varnode)

    def get_global_compare_record_map(self) -> 'dict[Varnode, VarnodeCompareRecord]':
        return self.globals_comparison.get_varnode_compare_record_map()

    def get_bytes(self, varnode_filter=None) -> int:
        return sum([ varnode_record.get_varnode().get_size() for varnode_record in self.get_varnode_compare_records() if varnode_filter is None or varnode_filter(varnode_record.get_varnode())])

    def bytes_overlapped(self, varnode_filter=None) -> int:
        return self.globals_comparison.bytes_overlapped(varnode_filter=varnode_filter) + sum([ cmp.varnode_bytes_overlapped(varnode_filter=varnode_filter) for cmp in self.get_function_compare_records() ])

    def get_varnode_records_matched_level(self, level: int) -> List[VarnodeCompareRecord]:
        return [ record for record in self.get_varnode_compare_records() if record.get_compare_level() >= level ]

    def get_primitive_varnode_records_matched_level(self, level: int) -> List[VarnodeCompareRecord]:
        return [ record for record in self.get_primitive_varnode_compare_records() if record.get_compare_level() >= level ]

    def get_unmatched_unoptimized_functions(self) -> List['UnoptimizedFunction']:
        return [ k for k, v in self.unoptimized_function_compare_map.items() if not v.is_comparison() ]

    def get_varnode_compare_records_from_unmatched_functions(self, primitive: bool = False) -> List[VarnodeCompareRecord]:
        varnode_compare_records = []
        for unopt in self.get_unmatched_unoptimized_functions():
            fn = unopt.get_function()
            for var in fn.get_vars() + fn.get_params():
                varnodes = var.get_varnodes()
                if primitive:
                    varnodes = sum([ varnode.flatten() for varnode in varnodes ], [])
                varnode_compare_records += [ VarnodeCompareRecord(varnode) for varnode in varnodes ]
        return varnode_compare_records

    def select_function_compare_records(self, function_cmp_record_cond=None) -> List['UnoptimizedFunctionCompareRecord']:
        return [ record for record in self.unoptimized_function_compare_map.values() if record is not None and (function_cmp_record_cond is None or function_cmp_record_cond(record)) ]

    def select_function_comparisons(self, function_cmp_record_cond=None, function_cmp2_cond=None) -> List['UnoptimizedFunctionCompare2']:
        return sum([ record.select_function_comparisons(function_cmp2_cond=function_cmp2_cond) for record in self.select_function_compare_records(function_cmp_record_cond=function_cmp_record_cond) ], [])

    def select_varnode_compare_records(self, function_cmp_record_cond=None, function_cmp2_cond=None, varnode_cmp_record_cond=None) -> List['VarnodeCompareRecord']:
        return self.globals_comparison.select_varnode_compare_records(varnode_cmp_record_cond=varnode_cmp_record_cond) \
            + sum([ record.select_varnode_compare_records(function_cmp2_cond=function_cmp2_cond, varnode_cmp_record_cond=varnode_cmp_record_cond) for record in self.select_function_compare_records(function_cmp_record_cond=function_cmp_record_cond) ], []) \
            + [ record for record in self.get_varnode_compare_records_from_unmatched_functions(primitive=False) if varnode_cmp_record_cond is None or varnode_cmp_record_cond(record) ]

    def select_primitive_varnode_compare_records(self, function_cmp_record_cond=None, function_cmp2_cond=None, varnode_cmp_record_cond=None) -> List['VarnodeCompareRecord']:
        return self.globals_comparison.select_primitive_varnode_compare_records(varnode_cmp_record_cond=varnode_cmp_record_cond) \
            + sum([ record.select_primitive_varnode_compare_records(function_cmp2_cond=function_cmp2_cond, varnode_cmp_record_cond=varnode_cmp_record_cond) for record in self.select_function_compare_records(function_cmp_record_cond=function_cmp_record_cond) ], []) \
            + [ record for record in self.get_varnode_compare_records_from_unmatched_functions(primitive=True) if varnode_cmp_record_cond is None or varnode_cmp_record_cond(record) ]

    def select_varnode_comparisons(self, function_cmp_record_cond=None, function_cmp2_cond=None, varnode_cmp_record_cond=None, varnode_cmp2_cond=None) -> List['VarnodeCompare2']:
        return self.globals_comparison.select_varnode_comparisons(varnode_cmp_record_cond=varnode_cmp_record_cond, varnode_cmp2_cond=varnode_cmp2_cond) \
            + sum([ record.select_varnode_comparisons(function_cmp2_cond=function_cmp2_cond, varnode_cmp_record_cond=varnode_cmp_record_cond, varnode_cmp2_cond=varnode_cmp2_cond) for record in self.select_function_compare_records(function_cmp_record_cond=function_cmp_record_cond) ], [])

    def select_primitive_varnode_comparisons(self, function_cmp_record_cond=None, function_cmp2_cond=None, varnode_cmp_record_cond=None, varnode_cmp2_cond=None) -> List['VarnodeCompare2']:
        return self.globals_comparison.select_primitive_varnode_comparisons(varnode_cmp_record_cond=varnode_cmp_record_cond, varnode_cmp2_cond=varnode_cmp2_cond) \
            + sum([ record.select_primitive_varnode_comparisons(function_cmp2_cond=function_cmp2_cond, varnode_cmp_record_cond=varnode_cmp_record_cond, varnode_cmp2_cond=varnode_cmp2_cond) for record in self.select_function_compare_records(function_cmp_record_cond=function_cmp_record_cond) ], [])

    # TODO: implement other select functions

    # at the top level, we may want to "flip" the comparison
    def flip(self) -> 'UnoptimizedProgramInfoCompare2':
        return __class__(self.right, self.left)

    def __hash__(self) -> int:
        return hash((self.left, self.right))

    def show_summary(self, indent=0) -> str:

        s = "\n----------GLOBAL COMPARISONS----------\n"
        s += "Globals:\n"
        s += self.globals_comparison.show_summary(indent=0)

        s += "Globals (flattened to primitives):\n"
        s += self.get_primitive_globals_comparison().show_summary(indent=0)

        s += "\n----------FUNCTION COMPARISONS----------\n"
        for record in self.unoptimized_function_compare_map.values():
            s += record.show_summary(indent=0)

        return indent_str(s, indent)

# A wrapper around a Function object that assumes that all variables
# & params have only 1 location throughout the course of the function.
class UnoptimizedFunction(object):
    def __init__(self, function: Function):
        self.function = function

    def get_function(self) -> Function:
        return self.function

    def get_pc_range(self) -> AddressRange:
        return self.function.get_pc_range()

    def get_start_pc(self) -> Address:
        return self.function.get_start_pc()

    def _get_vars_varnodes(self, vars: List[Variable]) -> List[Varnode]:
        varnodes = []
        for var in vars:
            vnodes = var.get_varnodes()
            if(len(vnodes) >= 1):
                varnodes.append(vnodes[0])
        return varnodes

    # get the varnodes representing parameters
    def get_param_varnodes(self) -> List[Varnode]:
        return self._get_vars_varnodes(self.function.get_params())

    # get the varnodes representing local variables within function
    def get_variable_varnodes(self) -> List[Varnode]:
        return self._get_vars_varnodes(self.function.get_vars())

    def get_param_varnodes_set(self) -> ConstPCVariableSetSnapshot:
        return ConstPCVariableSetSnapshot(self.get_param_varnodes())

    def get_variable_varnodes_set(self) -> ConstPCVariableSetSnapshot:
        return ConstPCVariableSetSnapshot(self.get_variable_varnodes())

    # get all varnodes tied to the function (params + locals)
    def get_varnodes(self) -> List[Varnode]:
        return self.get_param_varnodes() + self.get_variable_varnodes()

    def get_flattened_varnodes(self) -> List[Varnode]:
        return sum([ varnode.flatten() for varnode in self.get_varnodes() ], [])

    def __hash__(self) -> int:
        return hash(self.function)

    def __str__(self) -> str:
        pc_range = self.get_pc_range()
        return "<UnoptimizedFunction {} startpc={} endpc={}>".format(
            self.function.get_name() if self.function.get_name() is not None else "",
            pc_range.get_start(),
            pc_range.get_end()
        )

class UnoptimizedFunctionCompare2(object):
    def __init__(self,
        left: UnoptimizedFunction,
        right: UnoptimizedFunction
    ):
        self.left = left
        self.right = right

        self.pc_range_overlap = AddressRangeOverlap(self.left.get_pc_range(), self.right.get_pc_range())

        # initialize comparison fields to None
        self.rettype_compare2: Union[DataTypeCompare2, None] = None
        self.param_set_compare2: Union[ConstPCVariableSetSnapshotCompare2, None] = None
        self.variable_set_compare2: Union[ConstPCVariableSetSnapshotCompare2, None] = None

        # only if start PC of functions is equal do we compare the return types & variables/params
        if self.pc_range_start_aligned():
            self._compare()

    def _compare(self):
        # compare return types & store result
        self.rettype_compare2 = DataTypeCompare2(self.left.get_function().get_return_type(), self.right.get_function().get_return_type(), 0)

        # fetch the left & right param/variable sets
        left_param_set = ConstPCVariableSetSnapshot(self.left.get_param_varnodes())
        left_variable_set = ConstPCVariableSetSnapshot(self.left.get_variable_varnodes())
        left_varnode_set = ConstPCVariableSetSnapshot(self.left.get_varnodes())

        right_param_set = ConstPCVariableSetSnapshot(self.right.get_param_varnodes())
        right_variable_set = ConstPCVariableSetSnapshot(self.right.get_variable_varnodes())
        right_varnode_set = ConstPCVariableSetSnapshot(self.right.get_varnodes())

        # compare the parameter/variable sets and store
        self.param_set_compare2 = ConstPCVariableSetSnapshotCompare2(left_param_set, right_param_set)
        self.variable_set_compare2 = ConstPCVariableSetSnapshotCompare2(left_variable_set, right_variable_set)
        self.varnode_set_compare2 = ConstPCVariableSetSnapshotCompare2(left_varnode_set, right_varnode_set)


    def get_left(self) -> UnoptimizedFunction:
        return self.left

    def get_right(self) -> UnoptimizedFunction:
        return self.right

    def does_pc_range_overlap(self) -> bool:
        return self.pc_range_overlap.does_overlap()

    def pc_range_start_aligned(self) -> bool:
        return self.pc_range_overlap.start_aligned()

    def pc_range_end_aligned(self) -> bool:
        return self.pc_range_overlap.end_aligned()

    def pc_range_match(self) -> bool:
        return self.left.get_pc_range() == self.right.get_pc_range()

    def pc_range_bytes_overlapped(self) -> int:
        return self.pc_range_overlap.bytes_overlapped()

    def get_varnode_bytes_overlapped(self, varnode_filter=None) -> int:
        return self.get_primitive_variable_varnode_set_comparison().bytes_overlapped(varnode_filter=varnode_filter)

    def get_varnode_bytes(self, varnode_filter=None) -> int:
        return self.get_primitive_variable_varnode_set_comparison().get_bytes(varnode_filter=varnode_filter)

    def get_varnode_compare_records(self) -> List[VarnodeCompareRecord]:
        return self.varnode_set_compare2.get_varnode_compare_records()

    def get_primitive_params_varnode_set_comparison(self) -> ConstPCVariableSetSnapshotCompare2:
        return self.param_set_compare2.get_flattened_comparison()

    def get_primitive_variable_varnode_set_comparison(self) -> ConstPCVariableSetSnapshotCompare2:
        return self.variable_set_compare2.get_flattened_comparison()

    # includes params + locals
    def get_varnode_set_comparison(self) -> ConstPCVariableSetSnapshotCompare2:
        return self.varnode_set_compare2

    # includes params + locals (flattened to primitives)
    def get_primitive_varnode_set_comparison(self) -> ConstPCVariableSetSnapshotCompare2:
        return self.get_varnode_set_comparison().get_flattened_comparison()

    def get_primitive_varnode_compare_records(self) -> List[VarnodeCompareRecord]:
        return self.get_primitive_varnode_set_comparison().get_varnode_compare_records()

    def return_type_match(self) -> bool:
        return self.rettype_compare2.top_level_match() if self.rettype_compare2 is not None else False

    def get_return_type_comparison(self) -> Union[DataTypeCompare2, None]:
        return self.rettype_compare2

    def get_param_set_comparison(self) -> Union[ConstPCVariableSetSnapshotCompare2, None]:
        return self.param_set_compare2

    def get_variable_set_comparison(self) -> Union[ConstPCVariableSetSnapshotCompare2, None]:
        return self.variable_set_compare2

    def select_varnode_compare_records(self, varnode_cmp_record_cond=None) -> List['VarnodeCompareRecord']:
        return self.get_varnode_set_comparison().select_varnode_compare_records(varnode_cmp_record_cond=varnode_cmp_record_cond)

    def select_primitive_varnode_compare_records(self, varnode_cmp_record_cond=None) -> List['VarnodeCompareRecord']:
        return self.get_varnode_set_comparison().select_primitive_varnode_compare_records(varnode_cmp_record_cond=varnode_cmp_record_cond)

    def select_varnode_comparisons(self, varnode_cmp_record_cond=None, varnode_cmp2_cond=None) -> List['VarnodeCompare2']:
        return self.get_varnode_set_comparison().select_varnode_comparisons(varnode_cmp_record_cond=varnode_cmp_record_cond, varnode_cmp2_cond=varnode_cmp2_cond)

    def select_primitive_varnode_comparisons(self, varnode_cmp_record_cond=None, varnode_cmp2_cond=None) -> List['VarnodeCompare2']:
        return self.get_varnode_set_comparison().select_primitive_varnode_comparisons(varnode_cmp_record_cond=varnode_cmp_record_cond, varnode_cmp2_cond=varnode_cmp2_cond)

    def flip(self) -> 'UnoptimizedFunctionCompare2':
        return __class__(self.right, self.left)
    

    def __hash__(self) -> int:
        return hash((self.left, self.right))

    def __str__(self) -> str:
        return "<UnoptimizedFunctionCompare2 start_aligned={}>".format(
            self.pc_range_start_aligned()
        )

    def __repr__(self) -> str:
        return str(self)

    def show_summary(self, indent=0) -> str:
        s = ""
        if self.pc_range_start_aligned():
            s += "Parameters:\n"
            s += self.param_set_compare2.show_summary(indent=1)

            s += "Local Variables:\n"
            s += self.variable_set_compare2.show_summary(indent=1)

            s += "Flattened (Primitive) Parameters & Variables:\n"
            s += self.get_primitive_varnode_set_comparison().show_summary(indent=1)
        else:
            s = "NO FUNCTION MATCH\n"
        
        return indent_str(s, indent)

# Wraps an UnoptimizedFunction object.
# Stores and exposes information about this function's comparison
# with 0 or 1 other functions.
class UnoptimizedFunctionCompareRecord(object):
    def __init__(self,
        unoptimized_function: UnoptimizedFunction,
        comparison: Union[UnoptimizedFunctionCompare2, None]
    ):
        self.unoptimized_function = unoptimized_function
        self.comparison = comparison

    def get_unoptimized_function(self) -> UnoptimizedFunction:
        return self.unoptimized_function

    def is_comparison(self) -> bool:
        return self.comparison is not None

    def get_comparison(self) -> Union[UnoptimizedFunctionCompare2, None]:
        return self.comparison

    def varnode_bytes_overlapped(self) -> int:
        return 0 if not self.is_comparison() else self.comparison.get_varnode_bytes_overlapped()

    def get_varnode_compare_records(self) -> List[VarnodeCompareRecord]:
        return [] if not self.is_comparison() else self.comparison.get_varnode_compare_records()

    def get_primitive_varnode_compare_records(self) -> List[VarnodeCompareRecord]:
        return [] if not self.is_comparison() else self.comparison.get_primitive_varnode_compare_records()

    def _valid_comparison(self, function_cmp2_cond=None):
        return self.comparison is not None and (function_cmp2_cond is None or function_cmp2_cond(self.comparison))

    def select_function_comparisons(self, function_cmp2_cond=None) -> List['UnoptimizedFunctionCompare2']:
        return [self.comparison] if self._valid_comparison(function_cmp2_cond=function_cmp2_cond) else []

    def select_varnode_compare_records(self, function_cmp2_cond=None, varnode_cmp_record_cond=None) -> List['VarnodeCompareRecord']:
        return [] if not self._valid_comparison(function_cmp2_cond=function_cmp2_cond) else self.comparison.select_varnode_compare_records(varnode_cmp_record_cond=varnode_cmp_record_cond)

    def select_primitive_varnode_compare_records(self, function_cmp2_cond=None, varnode_cmp_record_cond=None) -> List['VarnodeCompareRecord']:
        return [] if not self._valid_comparison(function_cmp2_cond=function_cmp2_cond) else self.comparison.select_primitive_varnode_compare_records(varnode_cmp_record_cond=varnode_cmp_record_cond)

    def select_varnode_comparisons(self, function_cmp2_cond=None, varnode_cmp_record_cond=None, varnode_cmp2_cond=None) -> List['VarnodeCompare2']:
        return [] if not self._valid_comparison(function_cmp2_cond=function_cmp2_cond) else self.comparison.select_varnode_comparisons(varnode_cmp_record_cond=varnode_cmp_record_cond, varnode_cmp2_cond=varnode_cmp2_cond)

    def select_primitive_varnode_comparisons(self, function_cmp2_cond=None, varnode_cmp_record_cond=None, varnode_cmp2_cond=None) -> List['VarnodeCompare2']:
        return [] if not self._valid_comparison(function_cmp2_cond=function_cmp2_cond) else self.comparison.select_primitive_varnode_comparisons(varnode_cmp_record_cond=varnode_cmp_record_cond, varnode_cmp2_cond=varnode_cmp2_cond)

    def __hash__(self) -> int:
        return hash((self.unoptimized_function, self.comparison))

    def __str__(self) -> str:
        fname = self.unoptimized_function.get_function().get_name()
        return "<UnoptimizedFunctionCompareRecord name={} startpc={} compared={}>".format(
            fname if fname else "UNKNOWN",
            self.unoptimized_function.get_start_pc(),
            self.is_comparison()
        )

    def __repr__(self) -> str:
        return str(self)

    def show_summary(self, indent=0) -> str:
        s = str(self)
        if self.is_comparison():
            s += "\n"
            s += self.comparison.show_summary(indent=1)
        else:
            s += ": NO FUNCTION MATCH\n"

        return indent_str(s, indent)
