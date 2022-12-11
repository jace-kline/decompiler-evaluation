from typing import List, Tuple, Union
from lang import *
from lang_address import *
from lang_datatype import *
from type_lattice import *
from util import *

# should comparison between primitive types use '==' (True) or 'rough_equal' (False)?
EXACT_MATCH: bool = False

# the LatticeItem class to use
TYPE_LATTICE: type = Ariste_LatticeItem

# represents the quantification of the level/strength of a DataType comparison
class DataTypeCompareLevel(object):
    # no valid comparison could be made
    NO_MATCH = 0

    # left is a subset / member of right (possibly recursively) or vice-versa at given offset
    SUBSET = 1

    # both are primitive types and share a common ancestor in a type lattice
    PRIMITIVE_COMMON_ANCESTOR = 2

    # a "top-level" match -> the types are exactly equal
    MATCH = 3

    @staticmethod
    def to_string(code: int):
        _map = [
            "NO_MATCH",
            "SUBSET",
            "PRIMITIVE_COMMON_ANCESTOR",
            "MATCH"
        ]
        return _map[code]

    @staticmethod
    def range() -> range:
        return range(__class__.NO_MATCH, __class__.MATCH + 1)

class DataTypeCompareCode(object):
    # no valid comparison could be made
    NO_MATCH = 0

    # a "top-level" match -> the types are exactly equal
    MATCH = 1

    # left is a subset / member of right (possibly recursively) at given offset
    LEFT_SUBSET_RIGHT = 2

    # right is a subset / member of left (possibly recursively) at given offset
    RIGHT_SUBSET_LEFT = 3

    # both are primitive types and share a common ancestor in a type lattice
    PRIMITIVE_COMMON_ANCESTOR = 4

    @staticmethod
    def to_string(code):
        _map = [
            "NO_MATCH",
            "MATCH",
            "LEFT_SUBSET_RIGHT",
            "RIGHT_SUBSET_LEFT",
            "PRIMITIVE_COMMON_ANCESTOR"
        ]
        return _map[code]

    # DataTypeCompareCode -> DataTypeCompareLevel
    @staticmethod
    def to_level(code: int):
        _cls = DataTypeCompareCode
        _lvl_cls = DataTypeCompareLevel

        _map = {
            _cls.NO_MATCH: _lvl_cls.NO_MATCH,
            _cls.LEFT_SUBSET_RIGHT: _lvl_cls.SUBSET,
            _cls.RIGHT_SUBSET_LEFT: _lvl_cls.SUBSET,
            _cls.PRIMITIVE_COMMON_ANCESTOR: _lvl_cls.PRIMITIVE_COMMON_ANCESTOR,
            _cls.MATCH: _lvl_cls.MATCH
        }
        return _map[code]


# DataType object comparison between 2 objects
class DataTypeCompare2(object):
    def __init__(
        self,
        left: DataType,
        right: DataType,
        offset: int # offset from left start addr to right start addr
    ):
        self.left = left
        self.right = right

        # offset from left start addr to right start addr
        # if negative, indicates that right starts before left
        # == right var addr - left var addr
        self.offset = offset

        # initialize the descent and compare_code members to None
        self.left_descent = self.right_descent = None
        self.compare_code = DataTypeCompareCode.NO_MATCH
        self.primitive_comparison = None

        # if both are primitives and offset is 0, then try primitive comparison
        if self.left.is_primitive() and self.right.is_primitive() and self.offset == 0:
            self.primitive_comparison = DataTypePrimitiveCompare2(self.left, self.right)

        # perform the comparison logic & compute the compare_code
        self._compare()

        # TODO: implement the "flattened" primitive comparisons

    # sets self.left_descent, self.right_descent, self.compare_code
    def _compare(self):

        # if the types match exactly
        if self.exact_match():
                self.compare_code = DataTypeCompareCode.MATCH
                return
        
        # if both are primitives
        if self.primitive_comparison:

            if self.primitive_comparison.share_common_ancestor():
                self.compare_code = DataTypeCompareCode.PRIMITIVE_COMMON_ANCESTOR
                return

        # compute left descent?
        elif (self.left_before_right() or self.start_aligned()) and self.left_bigger_right() and self.left.is_complex():
            self.left_descent = DataTypeRecursiveDescent.descend_find_type_at_offset_recursive(
                self.left,
                self.offset,
                match_type=self.right,
                exact_match=EXACT_MATCH
            )

            # if there is a descent found, the right is a subset type of the left type
            if self.left_descent:
                self.compare_code = DataTypeCompareCode.RIGHT_SUBSET_LEFT
                return

        # compute right descent?
        elif (self.right_before_left() or self.start_aligned()) and self.right_bigger_left() and self.right.is_complex():
            self.right_descent = DataTypeRecursiveDescent.descend_find_type_at_offset_recursive(
                self.right,
                self.offset,
                match_type=self.left,
                exact_match=EXACT_MATCH
            )

            # if there is a descent found, the right is a subset type of the left type
            if self.right_descent:
                self.compare_code = DataTypeCompareCode.LEFT_SUBSET_RIGHT
                return

        # default: no match
        self.compare_code = DataTypeCompareCode.NO_MATCH

    def exact_match(self) -> bool:
        return self.offset == 0 and (self.left == self.right if EXACT_MATCH else self.left.rough_match(self.right))

    def top_level_match(self) -> bool:
        return self.compare_code == DataTypeCompareCode.MATCH

    def left_subset_right(self) -> bool:
        return self.compare_code == DataTypeCompareCode.LEFT_SUBSET_RIGHT

    def right_subset_left(self) -> bool:
        return self.compare_code == DataTypeCompareCode.RIGHT_SUBSET_LEFT

    def primitive_common_ancestor(self) -> bool:
        self.primitive_comparison.share_common_ancestor() if self.primitive_comparison else False

    def any_match(self) -> bool:
        return self.top_level_match() or self.left_subset_right() or self.right_subset_left()

    def no_match(self) -> bool:
        return self.compare_code == DataTypeCompareCode.NO_MATCH or not self.any_match()

    def get_left(self) -> DataType:
        return self.left

    def get_right(self) -> DataType:
        return self.right

    def get_offset(self) -> int:
        return self.offset

    def get_primitive_comparison(self) -> Union['DataTypePrimitiveCompare2', None]:
        return self.primitive_comparison

    def get_left_descent(self) -> Union[DataTypeRecursiveDescent, None]:
        return self.left_descent

    def get_right_descent(self) -> Union[DataTypeRecursiveDescent, None]:
        return self.right_descent

    def same_metatype(self) -> bool:
        return self.get_left().get_metatype() == self.get_right().get_metatype()

    def start_aligned(self):
        return self.get_offset() == 0

    def right_before_left(self) -> bool:
        return self.get_offset() < 0

    def left_before_right(self) -> bool:
        return self.get_offset() > 0

    # right size - left size
    def get_size_diff(self) -> int:
        return self.get_right().get_size() - self.get_left().get_size()

    def same_size(self) -> bool:
        return self.get_size_diff() == 0

    def left_bigger_right(self) -> bool:
        return self.get_size_diff() < 0

    def right_bigger_left(self) -> bool:
        return self.get_size_diff() > 0

    def bytes_overlapped(self) -> int:
        return 0 if self.no_match() else min(self.left.get_size(), self.right.get_size())

    def get_compare_code(self) -> int:
        return self.compare_code

    def get_compare_level(self) -> int:
        return DataTypeCompareCode.to_level(self.compare_code)

    def flip(self):
        return __class__(self.right, self.left, -1 * self.offset)

    def __str__(self):
        return "<DataTypeCompare2 left={} right={} offset={} compare_code={}>".format(
            self.left,
            self.right,
            self.offset,
            DataTypeCompareCode.to_string(self.compare_code)
        )

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash((self.left, self.right))

class DataTypePrimitiveCompareLevel(object):
    # no valid comparison could be made / no shared root node
    NO_MATCH = 0

    # the data types share a common ancestor node in the type lattice
    # but neither is a direct ancestor of the other
    COMMON_ANCESTOR = 1

    # left is a more precise form of right or vice-versa, according to type lattice
    # i.e., one is a direct ancestor of another
    DESCENT = 2

    # the primitive types are "equivalent" (same node in lattice)
    MATCH = 3

    @staticmethod
    def to_string(code):
        _map = [
            "NO_MATCH",
            "COMMON_ANCESTOR",
            "DIRECT_DESCENT",
            "MATCH"
        ]
        return _map[code]
    
class DataTypePrimitiveCompareCode(object):
    # no valid comparison could be made / no shared root node
    NO_MATCH = 0

    # the primitive types are equivalent (same node in lattice)
    MATCH = 1

    # left is a more precise form of right, according to type lattice
    LEFT_DESCENDANT_RIGHT = 2

    # right is a more precise form of left, according to type lattice
    RIGHT_DESCENDANT_LEFT = 3

    # the data types share a common ancestor node in the type lattice
    COMMON_ANCESTOR = 4

    @staticmethod
    def to_string(code):
        _map = [
            "NO_MATCH",
            "MATCH",
            "LEFT_DESCENDANT_RIGHT",
            "RIGHT_DESCENDANT_LEFT",
            "COMMON_ANCESTOR"
        ]
        return _map[code]

    @staticmethod
    def to_level(code):
        _cls = DataTypePrimitiveCompareCode
        _lvl_cls = DataTypePrimitiveCompareLevel
        _map = {
            _cls.NO_MATCH: _lvl_cls.NO_MATCH,
            _cls.LEFT_DESCENDANT_RIGHT: _lvl_cls.DESCENT,
            _cls.RIGHT_DESCENDANT_LEFT: _lvl_cls.DESCENT,
            _cls.COMMON_ANCESTOR: _lvl_cls.COMMON_ANCESTOR,
            _cls.MATCH: _lvl_cls.MATCH
        }
        return _map[code]

class DataTypePrimitiveCompare2(object):
    def __init__(
        self,
        left: DataType,
        right: DataType
    ):
        assert(left.is_primitive())
        assert(right.is_primitive())

        self.left = left
        self.right = right
        self.paths = None

        self.left_lattice_node = LatticeNode.from_datatype(TYPE_LATTICE, self.left)
        self.right_lattice_node = LatticeNode.from_datatype(TYPE_LATTICE, self.right)

        # initialize compare code
        self.compare_code: int = DataTypePrimitiveCompareCode.NO_MATCH

        # if either of the types cannot be translated to nodes, end early
        if self.left_lattice_node is None or self.right_lattice_node is None:
            return

        # compute the paths from the common ancestor path to each left & right
        self.paths = self.left_lattice_node.common_ancestor_paths(self.right_lattice_node)

        self._compute_compare_code()

    def _compute_compare_code(self):
        if self.left_lattice_node == self.right_lattice_node:
            self.compare_code = DataTypeCompareCode.MATCH

        elif self.left_descendant_right():
            self.compare_code = DataTypePrimitiveCompareCode.LEFT_DESCENDANT_RIGHT

        elif self.right_descendant_left():
            self.compare_code = DataTypePrimitiveCompareCode.RIGHT_DESCENDANT_LEFT

        elif self.share_common_ancestor():
            self.compare_code = DataTypePrimitiveCompareCode.COMMON_ANCESTOR

        else:
            self.compare_code = DataTypePrimitiveCompareCode.NO_MATCH

    def share_common_ancestor(self) -> bool:
        return self.paths is not None

    def left_descendant_right(self) -> bool:
        if not self.share_common_ancestor():
            return False

        leftpath, rightpath = self.paths
        return len(rightpath) == 1 and len(leftpath) > 1

    def right_descendant_left(self) -> bool:
        if not self.share_common_ancestor():
            return False

        leftpath, rightpath = self.paths
        return len(leftpath) == 1 and len(rightpath) > 1

    def get_left(self) -> DataType:
        return self.left

    def get_right(self) -> DataType:
        return self.right

    def get_lattice_type(self) -> type:
        return TYPE_LATTICE

    def get_compare_code(self) -> int:
        return self.compare_code

    def get_compare_level(self) -> int:
        return DataTypePrimitiveCompareCode.to_level(self.compare_code)

    def __str__(self) -> str:
        return "<DataTypePrimitiveCompare2 left={} right={} compare_code={}>".format(
            self.left,
            self.right,
            DataTypePrimitiveCompareCode.to_string(self.compare_code)
        )

    def __repr__(self) -> str:
        return self.__str__()

        
