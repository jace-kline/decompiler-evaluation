from typing import List, Tuple, Union
from lang import *
from lang_address import *
from lang_datatype import *
from lang_variable import *
from compare_datatype import *
from util import *

# represents a quanitification of the level/strength of a Varnode comparison
class VarnodeCompareLevel(object):
    NO_MATCH = 0 # not comparable or isn't compared with any others
    OVERLAP = 1 # non-aligned, non-subset overlap
    SUBSET = 2 # right var is a subset (member, subarray, etc.) of left var
    ALIGNED = 3 # addresses & size align, types don't
    MATCH = 4 # varnodes are equal

    @staticmethod
    def to_string(code: int):
        _map = [
            "NO_MATCH",
            "OVERLAP",
            "SUBSET",
            "ALIGNED",
            "MATCH"
        ]
        return _map[code]

    @staticmethod
    def range() -> range:
        return range(__class__.NO_MATCH, __class__.MATCH + 1)

class VarnodeCompare2Code(object):
    NO_OVERLAP = 0 # variables do not overlap at all
    OVERLAP = 1 # start not aligned, types not matched
    ALIGNED = 2 # start aligned, same size, types not matched
    MATCH = 3 # start aligned, same size, types match
    LEFT_CONTAINS_RIGHT = 4 # right matches a subset of left
    RIGHT_CONTAINS_LEFT = 5 # left matches a subset of right

    @staticmethod
    def to_string(code):
        _map = [
            "NO_OVERLAP",
            "OVERLAP",
            "ALIGNED",
            "MATCH",
            "LEFT_CONTAINS_RIGHT",
            "RIGHT_CONTAINS_LEFT"
        ]
        return _map[code]

    # VarnodeCompare2Code -> VarnodeCompareLevel
    @staticmethod
    def to_level(code: int):
        _cls = VarnodeCompare2Code
        _lvl_cls = VarnodeCompareLevel

        _map = {
            _cls.NO_OVERLAP: _lvl_cls.NO_MATCH,
            _cls.OVERLAP: _lvl_cls.OVERLAP,
            _cls.ALIGNED: _lvl_cls.ALIGNED,
            _cls.MATCH: _lvl_cls.MATCH,
            _cls.LEFT_CONTAINS_RIGHT: _lvl_cls.SUBSET,
            _cls.RIGHT_CONTAINS_LEFT: _lvl_cls.OVERLAP,
        }
        return _map[code]

# the result of comparing 2 Varnodes
# assume they are in the same address space (stack, absolute, etc.)
class VarnodeCompare2(object):
    def __init__(self,
        left: Varnode,
        right: Varnode
    ):
        self.left = left
        self.right = right

        # compute the AddressRangeOverlap between the 2 vars
        self.overlap: Union[AddressRangeOverlap, None] = self.get_left().get_addr_range().get_overlap(self.get_right().get_addr_range())

        # compute offset from left start addr to right start addr
        # = right addr - left addr
        self.offset: Union[int, None] = self.right.get_addr() - self.left.get_addr() if self.does_overlap() else None

        # compare the data types, but only if...
        # overlap exists, offset exists, and overlap is not "misaligned"
        
        self.datatype_comparison: Union[DataTypeCompare2, None] = None
        if (self.overlap is not None) and (self.offset is not None) and (not self.overlap.misaligned()):
            self.datatype_comparison = DataTypeCompare2(
                self.left.get_datatype(),
                self.right.get_datatype(),
                self.offset
            )

        self.compare_code: int = self._compute_compare_code()

        # if both left and right types are primitive, perform type lattice comparison
        # TODO: implement this

    def _compute_compare_code(self) -> int:
        code = VarnodeCompare2Code.NO_OVERLAP
        
        if not self.does_overlap():
            code = VarnodeCompare2Code.NO_OVERLAP
        elif self.is_aligned(): # same size & start addr
            code = VarnodeCompare2Code.ALIGNED
        else:
            code = VarnodeCompare2Code.OVERLAP


        if self.does_overlap() and self.datatype_comparison is not None: # assume we performed a DataType comparison
            if self.datatype_comparison.exact_match():
                code = VarnodeCompare2Code.MATCH
            elif self.datatype_comparison.right_subset_left():
                code = VarnodeCompare2Code.LEFT_CONTAINS_RIGHT
            elif self.datatype_comparison.left_subset_right():
                code = VarnodeCompare2Code.RIGHT_CONTAINS_LEFT

        return code

    # right.get_addr() - left.get_addr()
    def get_offset(self) -> Union[int, None]:
        return self.offset

    def does_overlap(self) -> bool:
        return self.get_overlap() is not None

    def get_left(self) -> Varnode:
        return self.left

    def get_right(self) -> Varnode:
        return self.right

    def get_overlap(self) -> Union[AddressRangeOverlap, None]:
        return self.overlap

    def get_compare_code(self) -> int:
        return self.compare_code

    def get_compare_level(self) -> int:
        return VarnodeCompare2Code.to_level(self.compare_code)

    def get_compare_code_str(self) -> str:
        return VarnodeCompare2Code.to_string(self.compare_code)

    def get_datatype_comparison(self) -> Union[DataTypeCompare2, None]:
        return self.datatype_comparison

    # same start addr?
    def is_start_aligned(self) -> bool:
        return self.overlap.start_aligned()

    # left size == right size?
    def is_same_size(self) -> bool:
        return self.get_size_diff() == 0

    # right size - left size
    def get_size_diff(self) -> int:
        return self.right.get_size() - self.left.get_size()

    # same start addr & same size
    def is_aligned(self) -> bool:
        return self.is_start_aligned() and self.is_same_size()

    # overlap, but start addrs don't align and the one that starts later extends past the end of the other
    def is_misaligned(self) -> bool:
        return self.overlap.misaligned()

    def bytes_overlapped(self) -> int:
        overlap = self.get_overlap()
        return overlap.bytes_overlapped() if overlap else 0

    def __hash__(self) -> int:
        return hash((self.left, self.right))

    def __str__(self) -> str:
        return "<VarnodeCompare2 left={} right={} compare_code={}>".format(
            self.left,
            self.right,
            self.get_compare_code_str()
        )

    def __repr__(self) -> str:
        return str(self)

    def show_summary(self, indent=0) -> str:
        s = "Comparison:\n\tother={}\n\tcompare_code={}".format(
            self.right,
            self.get_compare_code_str()
        )

        return indent_str(s, indent)

# wraps a Varnode object (Variable at a single Address)
# collects comparisons made between this varnode and others, and exposes
# methods for sharing information about those comparisons & status overall
class VarnodeCompareRecord(object):
    def __init__(self,
        varnode: Varnode
    ):
        self.varnode: Varnode = varnode

        # references to all the comparisons this variable is involved in
        # this varnode is always the "left" varnode in these comparisons
        self.varnode_comparison_map: dict[Varnode, VarnodeCompare2] = {}

    def get_compare_level(self) -> int:
        return max([VarnodeCompareLevel.NO_MATCH] + [cmp2.get_compare_level() for cmp2 in self.get_comparisons()])

    def compared_with(self) -> int:
        return len(self.varnode_comparison_map)

    def is_comparable(self) -> bool:
        # does addr exist AND the region
        addr = self.varnode.get_addr()
        return addr.get_region().is_range()

    def does_overlap(self) -> bool:
        return self.get_compare_level() >= VarnodeCompareLevel.OVERLAP

    def exact_match(self) -> bool:
        return self.get_compare_level() == VarnodeCompareLevel.MATCH

    def get_varnode(self) -> Varnode:
        return self.varnode

    def get_var(self) -> Variable:
        return self.varnode.get_var()

    def get_datatype(self) -> DataType:
        return self.get_var().get_datatype()

    def get_addr(self) -> Union[Address, None]:
        return self.varnode.get_addr()
    
    def get_addr_range(self) -> Union[AddressRange, None]:
        addr = self.get_addr()
        size = self.get_datatype().get_size()
        return AddressRange(addr, size=size) if addr and size else None

    def add_comparison(self, compare2: VarnodeCompare2):
        # add the Compare2 object to self.comparisons
        # verify that the &compare2.left == &self.varnode
        assert(compare2.get_left() is self.get_varnode())
        # ensure this varnode we are comparing against hasn't already
        # been inserted
        if compare2.get_right() not in self.varnode_comparison_map:
            self.varnode_comparison_map[compare2.get_right()] = compare2

    def get_compared_varnodes(self) -> List[Varnode]:
        return list(self.varnode_comparison_map.keys())

    def get_comparisons(self) -> List[VarnodeCompare2]:
        return list(self.varnode_comparison_map.values())

    def get_varnode_comparison_map(self) -> 'dict[Varnode, VarnodeCompare2]':
        return self.varnode_comparison_map

    def bytes_overlapped(self) -> int:
        overlapped = sum([ cmp.bytes_overlapped() for cmp in self.varnode_comparison_map.values() ])
        return min((overlapped, self.varnode.get_size()))

    def show_summary(self, indent=0) -> str:
        s = str(self)
        for cmp in self.varnode_comparison_map.values():
            s += "\n"
            s += cmp.show_summary(indent=1)
        s += "\n"

        return indent_str(s, indent)

    def __str__(self) -> str:
        return "<VarnodeCompareRecord varnode={} level={}>".format(
            self.varnode,
            self.get_compare_level()
        )

    def __repr__(self) -> str:
        return str(self)
