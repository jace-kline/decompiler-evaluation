from statistics import mean
from compare_unoptimized import *

# Variable base filter
# variable is not a parameter & has single location associated with it
def variable_base_filter(var: Variable) -> bool:
    return not var.is_param() \
        and var.is_single_loc()

# Varnode base filter
# varnode lives in stack or global region
# & its parent variable matches the variable base filter
def varnode_base_filter(varnode: Varnode) -> bool:
    parent_var = varnode.get_var()
    return varnode.get_addr().get_addrtype() in ( AddressType.ABSOLUTE, AddressType.STACK ) \
        and (variable_base_filter(parent_var) if parent_var is not None else True)

# VarnodeCompareRecord base filter
# record's varnode satisfies the Varnode base filter
def varnode_compare_record_base_filter(record: VarnodeCompareRecord) -> bool:
    return varnode_base_filter(record.get_varnode())

# FunctionCompareRecord base filter
# return True if the function comparison is not None
def function_compare_record_compared_filter(fn_cmp: UnoptimizedFunctionCompareRecord) -> bool:
    return fn_cmp.is_comparison()

def varnode_compare_records_matched_at_levels(records: Iterator[VarnodeCompareRecord], levels: Iterator[int]) -> List[VarnodeCompareRecord]:
    return [
        record for record in records
        if record.get_compare_level() in levels
    ]

def varnode_compare_records_metatypes(records: Iterator[VarnodeCompareRecord], metatypes: Iterator[int]) -> List[VarnodeCompareRecord]:
    return [
        record for record in records
        if record.get_varnode().get_datatype().get_metatype() in metatypes
    ]

def varnodes_from_compare_records(records: Iterator[VarnodeCompareRecord]) -> List[Varnode]:
    return [ record.get_varnode() for record in records ]

# Captures important information about the comparison for building sets of metrics
class MetricsInterface(object):
    def __init__(
        self,
        cmp: UnoptimizedProgramInfoCompare2
    ):

        # functions
        
        self.functions_truth = list(cmp.get_left().get_unoptimized_functions().values())

        self.functions_found = [ record.get_unoptimized_function() for record in cmp.select_function_compare_records() if function_compare_record_compared_filter(record) ]

        # varnodes
        
        self.varnode_compare_records = cmp.select_varnode_compare_records(
            function_cmp_record_cond=function_compare_record_compared_filter,
            varnode_cmp_record_cond=varnode_compare_record_base_filter
        )

        self.primitive_varnode_compare_records = cmp.select_primitive_varnode_compare_records(
            function_cmp_record_cond=function_compare_record_compared_filter,
            varnode_cmp_record_cond=varnode_compare_record_base_filter
        )

        # array comparisons

        self.array_comparisons = cmp.select_varnode_comparisons(
            varnode_cmp_record_cond=varnode_compare_record_base_filter,
            varnode_cmp2_cond=lambda record: record.get_left().get_datatype().get_metatype() == MetaType.ARRAY and record.get_right().get_datatype().get_metatype() == MetaType.ARRAY
        )


    def filter_varnode_compare_records(
        self,
        primitive: bool = False,
        metatypes: List[int] = None,
        compare_levels: List[int] = None
    ) -> List[VarnodeCompareRecord]:
        records = self.varnode_compare_records if not primitive else self.primitive_varnode_compare_records
        if metatypes:
            records = varnode_compare_records_metatypes(records, metatypes)
        if compare_levels:
            records = varnode_compare_records_matched_at_levels(records, compare_levels)
        return records

class MetricsSet(object):
    pass

class FunctionsMetricsSet(MetricsSet):
    def __init__(
        self,
        interface: MetricsInterface
    ):
        self.functions_truth = len(interface.functions_truth)
        self.functions_found = len(interface.functions_found)
        self.functions_missed = self.functions_truth - self.functions_found
        self.functions_found_fraction = self.functions_found / self.functions_truth

    def __dict__(self) -> dict:
        return {
            "Ground truth functions": self.functions_truth,
            "Functions found": self.functions_found,
            "Functions missed": self.functions_missed,
            "Functions found fraction": self.functions_found_fraction
        }

class VarnodesMetricsSet(MetricsSet):
    def __init__(
        self,
        interface: MetricsInterface,
        primitive: bool = False,
        metatype: int = None
    ):
        self.primitive = primitive
        self.metatype = metatype

        self.varnodes_truth = len(interface.filter_varnode_compare_records(
            primitive=primitive,
            metatypes=(metatype,) if metatype is not None else None
        ))

        self.varnode_compare_score = 0
        self.matched_at_level = {}
        for level in VarnodeCompareLevel.range():
            matched_at = len(interface.filter_varnode_compare_records(
                primitive=primitive,
                metatypes=(metatype,) if metatype is not None else None
            ))
            self.varnode_compare_score += level * matched_at
            self.matched_at_level[level] = matched_at

        # normalize to be in [0,1]
        self.varnode_compare_score = self.varnode_compare_score / self.varnodes_truth * VarnodeCompareLevel.MATCH if self.varnodes_truth is not None else None

        self.varnodes_missed = self.varnodes_matched_at_level(VarnodeCompareLevel.NO_MATCH)
        self.varnodes_partially_recovered = self.varnodes_truth - self.varnodes_missed
        self.varnodes_partially_recovered_fraction = self.varnodes_partially_recovered / self.varnodes_truth if self.varnodes_truth is not None else None
        self.varnodes_exactly_recovered = self.varnodes_matched_at_level(VarnodeCompareLevel.MATCH)
        self.varnodes_exactly_recovered_fraction = self.varnodes_exactly_recovered / self.varnodes_truth if self.varnodes_truth is not None else None

    def varnodes_matched_at_level(self, level: int) -> int:
        return self.matched_at_level.get(level, 0)

    def __dict__(self) -> dict:
        suffix = ""
        if self.primitive:
            suffix += " (decomposed)"
        if self.metatype is not None:
            suffix += " (metatype={})".format(MetaType.repr(self.metatype))

        d = { "Ground truth varnodes{}".format(suffix): self.varnodes_truth }
        for level in VarnodeCompareLevel.range():
            d["Varnodes matched @ level={}{}".format(VarnodeCompareLevel.to_string(level), suffix)] = self.varnodes_matched_at_level(level)
        d["Varnode comparison score [0,1]{}".format(suffix)] = self.varnode_compare_score
        d["Varnodes partially recovered fraction{}".format(suffix)] = self.varnodes_partially_recovered_fraction
        d["Varnodes exactly recovered fraction{}".format(suffix)] = self.varnodes_exactly_recovered_fraction

        return d

## length inaccuracy (elements) of an array comparison
def array_elements_error(cmp: VarnodeCompare2) -> int:
    return abs(cmp.get_left().get_datatype().get_num_elements() - cmp.get_right().get_datatype().get_num_elements())

## size inaccuracy (bytes) of an array comparison
def array_size_error(cmp: VarnodeCompare2) -> int:
    return abs(cmp.get_left().get_size() - cmp.get_right().get_size())

class ArrayComparisonsMetricsSet(MetricsSet):
    def __init__(
        self,
        interface: MetricsInterface
    ):
        self.array_comparisons = len(interface.array_comparisons)

        array_length_errors = [ array_elements_error(cmp) for cmp in self.array_comparisons ]
        self.array_length_avg_error = mean(array_length_errors) if array_length_errors else None
        self.array_length_max_error = max(array_length_errors) if array_length_errors else None
        
        array_size_errors = [ array_size_error(cmp) for cmp in self.array_comparisons ]
        self.array_size_avg_error = mean(array_size_errors) if array_size_errors else None
        self.array_size_max_error = max(array_size_errors) if array_size_errors else None
    



