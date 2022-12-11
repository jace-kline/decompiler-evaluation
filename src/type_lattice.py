from enum import Enum, auto, unique
from typing import List, Union, Tuple
from lang_datatype import *

# The interface to implement if you want to be the "item type" that is stored within a lattice
# Each item must know how to construct its parent and its children
# Each item must be comparable to another
# Each item must be constructable from a DataType object
class LatticeItemType(object):
    def parent(self) -> Union['LatticeItemType', None]:
        pass

    def children(self) -> List['LatticeItemType']:
        pass

    def __eq__(self) -> bool:
        pass

    @staticmethod
    def from_datatype(dtype: DataType) -> Union['LatticeItemType', None]:
        pass

# Wraps the LatticeItemType object and exposes higher-level methods for traversal, etc.
class LatticeNode(object):
    def __init__(
        self,
        item: LatticeItemType
    ):
        self.item = item

    def get_item(self) -> LatticeItemType:
        return self.item

    def parent(self) -> Union['LatticeNode', None]:
        return LatticeNode(self.item.parent()) if not self.is_root() else None

    def children(self) -> List['LatticeNode']:
        return [ LatticeNode(item) for item in self.item.children() ]
    
    def is_root(self) -> bool:
        return self.item.parent() is None

    def is_leaf(self) -> bool:
        return not self.item.children()

    def is_inner(self) -> bool:
        return not self.is_root() and not self.is_inner()

    def height(self) -> int:
        return 0 if self.is_leaf() else 1 + max([ child.height() for child in self.children() ])

    def depth(self) -> int:
        return 0 if self.is_root() else 1 + self.parent().depth()

    def path_from_root(self) -> List['LatticeNode']:
        return [self] if self.is_root() else self.parent().path_from_root() + [self]

    def path_to_root(self) -> List['LatticeNode']:
        return reversed(self.path_from_root())

    # the paths from the common ancestor node to self and other
    # returns None if no common ancestor exists
    def common_ancestor_paths(self, other: 'LatticeNode') -> Union[Tuple[List['LatticeNode'], List['LatticeNode']], None]:
        self_path = []
        for node in self.path_to_root():
            self_path.append(node)

            other_path = []
            for othernode in other.path_to_root():
                other_path.append(othernode)

                # found common ancestor?
                if node == othernode:
                    # reverse the paths such that the common ancestor is the 0th element
                    return ( list(reversed(self_path)), list(reversed(other_path)) )
        # fall through -> no common ancestor
        return None

    def common_ancestor(self, other) -> Union['LatticeNode', None]:
        common_paths = self.common_ancestor_paths(other)
        return common_paths[0][0] if common_paths is not None else None

    def __eq__(self, other: 'LatticeNode') -> bool:
        return self.item == other.item

    def __str__(self) -> str:
        return "<LatticeNode {}>".format(self.item)

    def __repr__(self) -> str:
        return self.__str__()

    @staticmethod
    def from_datatype(itemtype: type, dtype: DataType) -> Union['LatticeNode', None]:
        item: Union[itemtype, None] = itemtype.from_datatype(dtype)
        return None if item is None else LatticeNode(item)

# Implements the LatticeItemType interface
@unique
class Ariste_NodeType(Enum):
    ROOT = auto()
    CODE = auto()
    DATA = auto()
    FLOAT = auto()
    NUM = auto()
    PTR = auto()
    INT = auto()
    UINT = auto()

    @staticmethod
    def _children_map() -> 'dict[Ariste_NodeType, List[Ariste_NodeType]]':
        _cls = Ariste_NodeType
        return {
            _cls.ROOT: [_cls.CODE, _cls.DATA],
            _cls.DATA: [_cls.FLOAT, _cls.NUM],
            _cls.NUM: [_cls.PTR, _cls.INT, _cls.UINT]
        }

    @staticmethod
    def _parent_map() -> 'dict[Ariste_NodeType, Union[Ariste_NodeType, None]]':
        _map = {}
        for k, vs in Ariste_NodeType._children_map().items():
            for v in vs:
                _map[v] = k
        return _map


    def parent(self) -> Union['Ariste_NodeType', None]:
        return self._parent_map().get(self, None)

    def children(self) -> List['Ariste_NodeType']:
        return self._children_map().get(self, [])

    # uses a type's metatype to determine which nodetype to map to
    @staticmethod
    def from_datatype(dtype: DataType) -> Union['Ariste_NodeType', None]:
        _cls = Ariste_NodeType
        _metatype = dtype.get_metatype()

        if _metatype == MetaType.INT:
            return _cls.INT if dtype.is_signed() else _cls.UINT

        elif _metatype == MetaType.FLOAT:
            return _cls.FLOAT

        elif _metatype == MetaType.POINTER:
            return _cls.PTR

        elif _metatype == MetaType.UNDEFINED:
            return _cls.DATA

        else:
            return _cls.ROOT


# Implements the LatticeItemType interface
class Ariste_LatticeItem(object):

    VALID_BIT_SIZES = [1, 8, 16, 32, 64, 80]

    def __init__(self,
        nodetype: Ariste_NodeType, # also implements the LatticeItemType interface
        bits: Union[int, None] = None # the number of bits this primitive type is
    ):
        self.nodetype = nodetype
        self.bits = bits # number of bits

    def parent(self) -> Union['Ariste_LatticeItem', None]:
        # if we are "sized" data, our parent is unsized data
        if self.nodetype == Ariste_NodeType.DATA and self.bits is not None:
            return __class__(Ariste_NodeType.DATA, bits=None)

        # if we are "sized" code, our parent is unsized code
        elif self.nodetype == Ariste_NodeType.CODE and self.bits is not None:
            return __class__(Ariste_NodeType.CODE, bits=None)

        # otherwise, the structure follows the Ariste_NodeType structure with the bits the same
        else:
            nodetype_parent = self.nodetype.parent()
            return __class__(nodetype_parent, bits=self.bits) if nodetype_parent is not None else None

    def children(self) -> List['Ariste_LatticeItem']:
        if self.nodetype == Ariste_NodeType.DATA:
            if self.bits is None:
                return [ __class__(Ariste_NodeType.DATA, bits=bits) for bits in Ariste_LatticeItem.VALID_BIT_SIZES ]
            elif self.bits == 1:
                return []
            elif self.bits == 80:
                return [ __class__(Ariste_NodeType.FLOAT, bits=self.bits) ]
        
        return [ __class__(nodetype, size=self.bits) for nodetype in self.nodetype.children() ]

    def __eq__(self, other: 'Ariste_LatticeItem') -> bool:
        return self.nodetype == other.nodetype and self.bits == other.bits

    def __str__(self) -> str:
        return "<Ariste_LatticeItem nodetype={} bits={}>".format(self.nodetype, self.bits)

    def __repr__(self) -> str:
        return self.__str__()

    # construct a lattice item from a DataType object
    @staticmethod
    def from_datatype(dtype: DataType) -> Union['Ariste_LatticeItem', None]:
        _nodetype = Ariste_NodeType.from_datatype(dtype)
        if _nodetype is None:
            return None
        
        _bytes = dtype.get_size()
        bits = None if _bytes is None or _bytes == 0 else _bytes * 8

        if bits is None:
            return None
        
        return Ariste_LatticeItem(_nodetype, bits=bits)


if __name__ == "__main__":
    float80 = LatticeNode(Ariste_LatticeItem(Ariste_NodeType.FLOAT, bits=80))
    uint16 = LatticeNode(Ariste_LatticeItem(Ariste_NodeType.UINT, bits=16))

    print(float80.common_ancestor_paths(uint16))

