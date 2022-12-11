
# enum of "meta types"
class MetaType(object):
    """
    Enumeration of "meta types".

    INT: int/char
    FLOAT: float/double
    POINTER: pointer to another type
    ARRAY: a sequence of elements of another type
    UNION: an "either-or" disjunctive type sharing the same memory space
    UNDEFINED: a sized type of unknown classification
    VOID: a 0-sized type
    FUNCTION_PROTOTYPE: a type containing a return type + list of parameter types
    TYPEDEF: a type that exists as an alias of another type
    ENUM: a type consisting of a discrete subset of "tagged" integers
    QUALIFIER: a "wrapper" type that qualifies another type (const, volatile, etc.)
    STRING: a high-level string, usually represented as a null-terminated char array
    """
    INT = 0
    FLOAT = 1
    POINTER = 2
    ARRAY = 3
    STRUCT = 4
    UNION = 5
    UNDEFINED = 6
    VOID = 7
    FUNCTION_PROTOTYPE = 8
    TYPEDEF = 9
    ENUM = 10
    QUALIFIER = 11
    STRING = 12

    @staticmethod
    def repr(metatype_code):
        metatypes = [
            "INT",
            "FLOAT",
            "POINTER",
            "ARRAY",
            "STRUCT",
            "UNION",
            "UNDEFINED",
            "VOID",
            "FUNCTION_PROTOTYPE",
            "TYPEDEF",
            "ENUM",
            "QUALIFIER",
            "STRING"
        ]
        return metatypes[metatype_code]


# Tracks a path into a composite data type
# Provides methods for querying information about the path
class DataTypeRecursiveDescent(object):

    # the relationship a record has to its parent (or ROOT)
    class Relationship(object):
        ARRAY_ELEMENT = 0 # element of parent array
        STRUCT_MEMBER = 1 # member of parent struct
        UNION_MEMBER = 2 # member of parent union
        SUBSET = 3 # a subarray, partial struct, etc.

        @staticmethod
        def to_string(code):
            _cls = DataTypeRecursiveDescent.Relationship
            _map = {
                _cls.ARRAY_ELEMENT: "ARRAY_ELEMENT",
                _cls.STRUCT_MEMBER: "STRUCT_MEMBER",
                _cls.UNION_MEMBER: "UNION_MEMBER",
                _cls.SUBSET: "SUBSET"
            }
            return _map[code]

    # This class holds information about recursive descent of subtypes
    # in a type tree. Captures chain of recurses + offsets.
    class DescentRecord(object):
        def __init__(self, relationship, offset, dtype):
            # the relationship tag (int) that relates this type to its parent
            self.relationship = relationship
            # the DataType of this node
            self.dtype = dtype
            # the offset from the start address of the immediate parent type
            self.offset = offset

        def get_relationship(self):
            return self.relationship

        def get_datatype(self):
            return self.dtype

        def get_offset(self):
            return self.offset

        def __str__(self):
            return "<DescentRecord {} offset={} dtype={}>".format(
                DataTypeRecursiveDescent.Relationship.to_string(self.relationship),
                self.offset,
                self.dtype
            )

        def __repr__(self):
            return self.__str__()

    # root : DataType (the root datatype to recurse into)
    # path : [DescentRecord] (possibly empty list if root matched)
    def __init__(self, root, path):
        # self.root: DataType
        self.root = root
        # self.path: [DescentRecord]
        self.path = path

    # Create a DataTypeRecursiveDescent object for finding a given type at an offset of a root type
    @staticmethod
    def descend_find_type_at_offset_recursive(root, offset, match_type=None, exact_match=False):
        res = root.get_type_at_offset_recursive(offset, match_type=match_type, exact_match=exact_match)
        return DataTypeRecursiveDescent(root, res) if res is not None else None

    def get_path(self):
        return self.path

    def no_descent(self):
        return len(self.path) == 0

    def get_root(self):
        return self.root
    
    def get_leaf(self):
        return self.path[-1]

    def get_total_offset(self):
        return sum([ record.offset for record in self.path ])

    def get_depth(self):
        return len(self.path)

    # returns path record at the ith level deep
    def __getitem__(self, i):
        return self.path[i]

    def __str__(self):
        return "<DataTypeRecursiveDescent root={} offset={} depth={}>".format(
            self.root,
            self.get_total_offset(),
            self.get_depth()
        )

    def __repr__(self):
        return str(self)

class DataType(object):
    """
    The base class for representing a data type.
    Contains a "meta type" and size.
    Subclasses contain more specified information.
    """
    def __init__(self, metatype=None, size=None):
        """
        metatype: field of MetaType class
            The meta type of the datatype.
            options = INT | FLOAT | POINTER | ARRAY | STRUCT | UNION | UNDEFINED | VOID | FUNCTION_PROTOTYPE | TYPEDEF | ENUM | QUALIFIER | STRING
        size: int
            The total size of the datatype
        """
        self.metatype = metatype
        self.size = size

    def get_metatype(self):
        return self.metatype

    def get_size(self):
        return self.size

    # by default, assume a primitive type (doesn't reference any other types)
    # override in children
    def is_primitive(self):
        return True

    # Is this type a complex type? -> References "sub-components"?
    # override in children
    def is_complex(self):
        return False

    # does this actually occupy a certain amount of address space?
    # or is it an abstract type (e.g. function prototype)?
    def is_sized(self):
        return True

    # Flatten this datatype into an iterator of (offset, primitive type) pairs
    # May return None if doesn't make sense for the datatype (e.g. function prototype)
    def flatten(self):
        if self.is_primitive():
            yield (0, self)
        else:
            raise NotImplementedError()

    # how many layers of "composition" does this type contain?
    # 0 for primitive
    # for composite types, 1 + max composition level of subtypes
    def composition_level(self):
        return 0

    # get the component type that starts at a given offset, possibly restricting size
    # int -> DescentRecord | None
    # DescentRecord ~= (relationship, offset_to_subtype, subtype)
    def get_component_type_at_offset(self, offset, size=None):
        return None

    # get the component type that includes a given offset
    # int -> DescentRecord | None
    # DescentRecord ~= (relationship, offset_to_subtype, subtype)
    def get_component_type_containing_offset(self, offset):
        return None

    # Get a path (list) of DescentRecord objects that represent
    # "nesting into" this particular type such that the leaf record
    # sufficiently satisfies the offset and possibly match_type conditions.
    # If this type itself matches, return an empty path [].
    def get_type_at_offset_recursive(self, offset, match_type=None, exact_match=False):
        # base case: offset == 0 and size matches (if size given)
        # return empty path since we didn't have to recurse at all
        if offset == 0 \
            and (match_type is None \
                or self == match_type \
                or (not exact_match and self.rough_match(match_type))
            ):
            return []


        # otherwise, try to recurse, but only if complex type
        elif not self.is_complex():
            return None

        # if we are here, we know that self is a complex type with sub-components
        # record: DescentRecord | None

        # try to get component type at exact offset (more precise, size specified)
        size = match_type.get_size() if match_type is not None else None
        record = self.get_component_type_at_offset(offset, size=size)

        # if that fails, get the component type containing the offset
        record = record if record is not None else self.get_component_type_containing_offset(offset)
        if record is None:
            return None
        
        # the remainder of the offset that must be handled by the subtype recursive call
        recurse_offset = offset - record.get_offset()

        # recurse : [DescentRecord] | None
        recurse = record.get_datatype().get_type_at_offset_recursive(recurse_offset, match_type, exact_match)
        if recurse is not None:
            # add the record to the top of the descent path and return
            return [record] + recurse

        return None

    # rough equality
    # we consider DataType objects to be a "rough match" if they have the same metatype and size
    def rough_match(self, other):
        return self.get_metatype() == other.get_metatype() and self.get_size() == other.get_size()

    # exact equality
    # override in child classes
    def __eq__(self, other):
        return self.rough_match(other)

    def __str__(self):
        pass # implement in children

    def __hash__(self):
        return hash((self.metatype, self.size))

class DataTypeFunctionPrototype(DataType):
    """
    Data type representing a function prototype.
    Could be pointed to by function pointer.
    Used as 'proto' argument for creating a Function object.
    """
    def __init__(self, rettype=None, paramtypes=None, variadic=False):
        super(DataTypeFunctionPrototype, self).__init__(
            metatype=MetaType.FUNCTION_PROTOTYPE,
            size=0
        )
        self.rettype = rettype
        self.paramtypes = paramtypes
        self.variadic = variadic

    # by default, assume a primitive type (doesn't reference any other types)
    # override in children
    def is_primitive(self):
        return False

    # Is this type a complex type? -> References "sub-components"?
    # override in children
    def is_complex(self):
        return True

    def is_sized(self):
        return False

    # this operation doesn't really make sense for a function prototype
    # since this doesn't occupy any space in memory
    def flatten(self):
        return None

    def __eq__(self, other):
        return self.rough_match(other) \
            and self.rettype == other.rettype \
            and self.paramtypes == other.paramtypes \
            and self.variadic == other.variadic

    def __str__(self):
        s = "("
        for i, paramtype in enumerate(self.paramtypes):
            s += str(paramtype)
            if i + 1 < len(self.paramtypes):
                s += ", "
        if self.variadic:
            s += "[...]"
        s += ") -> " + str(self.rettype)
        return s
    
    def __hash__(self):
        return hash((self.metatype, self.size, self.rettype, tuple(self.paramtypes), self.variadic))

class DataTypeInt(DataType):
    """
    Data type representing int/char, possibly unsigned.
    """
    def __init__(self, size=None, signed=True):
        super(DataTypeInt, self).__init__(
            metatype=MetaType.INT,
            size=size
        )
        self.signed = signed

    def is_signed(self):
        return self.signed

    def __eq__(self, other):
        return self.rough_match(other) and self.signed == other.signed

    def __str__(self):
        s = ""
        if not self.signed:
            s += "unsigned "

        if self.size == 1:
            s += "char"
        else:
            s += "int" + str(self.size)
        return s

    def __hash__(self):
        return hash((self.metatype, self.size, self.signed))


class DataTypeFloat(DataType):
    """
    Datatype representing float/double.
    """
    def __init__(self, size=None):
        super(DataTypeFloat, self).__init__(
            metatype=MetaType.FLOAT,
            size=size
        )

    def __str__(self):
        return "float" + str(self.size)

    def __hash__(self):
        return hash((self.metatype, self.size))


class DataTypeUndefined(DataType):
    """
    A sized but undefined datatype.
    """
    def __init__(self, size=None):
        super(DataTypeUndefined, self).__init__(
            metatype=MetaType.UNDEFINED,
            size=size
        )

    def __str__(self):
        return "undefined" + str(self.size)

    def __hash__(self):
        return hash((self.metatype, self.size))

class DataTypeVoid(DataType):
    """
    Void datatype (size = 0).
    """
    def __init__(self):
        super(DataTypeVoid, self).__init__(
            metatype=MetaType.VOID,
            size=0
        )
    
    def __str__(self):
        return "void"

    def __hash__(self):
        return hash((self.metatype, self.size))


class DataTypePointer(DataType):
    """
    Datatype representing a pointer of some base type.
    """
    def __init__(self, basetype=None, size=None):
        """
        basetype: DataType
            The type of the object being pointed to
        """
        super(DataTypePointer, self).__init__(
            metatype=MetaType.POINTER,
            size=size
        )
        self.basetype = basetype

    def is_primitive(self):
        return True

    def is_complex(self):
        return False

    def __eq__(self, other):
        return self.rough_match(other) and self.basetype.rough_match(other.basetype)

    def __str__(self):
        return str(self.basetype) + " *"

    def __hash__(self):
        # approximate the basetype since it may be recursive/self-referential
        basetype_approx = (self.basetype.get_metatype(), self.basetype.get_size())
        return hash((self.metatype, self.size, basetype_approx))


class DataTypeArray(DataType):
    def __init__(self, basetype=None, dimensions=None, size=None):
        """
        basetype: DataType
            The type of the elements in the array
        length: int
            The length of the array. -1 if unknown.
        size: int
            The total number of bytes allocated to the array. -1 if unknown.
        """

        super(DataTypeArray, self).__init__(
            metatype=MetaType.ARRAY,
            size=size
        )
        self.basetype = basetype
        self.dimensions = dimensions

    @staticmethod
    def compute_flat_length(dims):
        length = 1
        for dim in dims:
            length *= dim
        return length

    @staticmethod
    def compute_size(dims, basetype_size):
        return DataTypeArray.compute_flat_length(dims) * basetype_size

    def _resolve(self):
        if self.size is None:
            if self.dimensions is not None and self.basetype is not None:
                self.size = DataTypeArray.compute_size(self.dimensions, self.basetype.get_size())
            else:
                self.size = 0

        elif self.dimensions is None:
            if self.size is not None and self.basetype is not None:
                self.dimensions = (self.size // self.basetype.get_size(),)

    def get_basetype(self):
        return self.basetype

    def get_num_elements(self):
        return DataTypeArray.compute_flat_length(self.dimensions)

    def num_dimensions(self):
        return len(self.dimensions)

    def get_dimensions(self):
        return self.dimensions

    def dimensions_unknown(self):
        return len(self.dimensions) == 0 or self.dimensions is None

    # by default, assume a primitive type (doesn't reference any other types)
    # override in children
    def is_primitive(self):
        return False

    # Is this type a complex type? -> References "sub-components"?
    # override in children
    def is_complex(self):
        return True

    def composition_level(self):
        return 1 + self.basetype.composition_level()

    # if this array has greater than 1 dimension, flatten it down to 1 dimension
    def to_1d(self):
        if self.num_dimensions() == 1:
            return self
        else:
            dims = (DataTypeArray.compute_flat_length(self.dimensions),)
            
            return DataTypeArray(
                basetype=self.basetype,
                dimensions=dims,
                size=DataTypeArray.compute_size(dims, self.basetype.get_size())
            )

    def flatten(self):
        # iterate over each element offset from the base of the array
        for i in range(0, self.get_num_elements()):
            offset = i * self.basetype.get_size()
            # for each element offset, we flatten the basetype into its primitives
            # and return them 1 at a time
            for (off, primitive) in self.basetype.flatten():
                yield (offset + off, primitive)

    # get the component type that starts at a given offset, possibly restricting size
    # int -> DescentRecord | None
    def get_component_type_at_offset(self, offset, size=None):
        assert (self.size is not None)
        if self.dimensions_unknown():
            return None

        # check for alignment, size, etc.
        if offset % self.basetype.get_size() != 0 \
            or (offset >= self.size) \
            or (size is not None and (size % self.basetype.get_size() != 0 or offset + size > self.size)):
            return None

        # default scenario is that we are nesting into element of the array
        relationship = DataTypeRecursiveDescent.Relationship.ARRAY_ELEMENT
        subtype = self.basetype

        # if specified size is a multiple (> 1) of basetype size, then construct a sub array type
        if size is not None:
            sublength = size // self.basetype.size
            if 1 < sublength < self.get_num_elements():
                relationship = DataTypeRecursiveDescent.Relationship.SUBSET
                subtype = DataTypeArray(basetype=self.basetype, dimensions=(sublength,), size=self.basetype.get_size() * sublength)
            
        return DataTypeRecursiveDescent.DescentRecord(relationship, offset, subtype)
            

    # get the component type that includes a given offset
    # return the actual offset the component type was found at
    # actual offset <= offset
    # int -> DescentRecord | None
    def get_component_type_containing_offset(self, offset):
        
        # checks
        if self.dimensions_unknown() or not (0 <= offset < self.size):
            return None

        # actual_offset = the actual offset to the desired element
        actual_offset = offset - (offset % self.basetype.get_size())
        return DataTypeRecursiveDescent.DescentRecord(
            DataTypeRecursiveDescent.Relationship.ARRAY_ELEMENT,
            actual_offset,
            self.basetype
        )

    def __eq__(self, other):
        return self.rough_match(other) \
            and self.basetype == other.basetype \
            and self.dimensions == other.dimensions

    def __str__(self):
        return "<ARRAY subtype={} dimensions={} size={}>".format(str(self.basetype), self.dimensions, self.size)

    def __hash__(self):
        return hash((self.metatype, self.size, self.basetype, self.dimensions))


class DataTypeStruct(DataType):
    """
    Datatype representing a C struct.
    """
    ALIGN_SIZE = 4 # assume we are aligning on 4-byte boundaries

    def __init__(self, name=None, membertype_offsets=None, size=None):
        self.name = name
        self.membertype_offsets = membertype_offsets
        super(DataTypeStruct, self).__init__(
            metatype=MetaType.STRUCT,
            size=size
        )

    def get_membertypes(self):
        return [ memtype for _, memtype in self.membertype_offsets ]

    def get_member_offsets(self):
        return [ offset for offset, _ in self.membertype_offsets ]

    def get_number_members(self):
        return len(self.membertype_offsets)

    def _resolve_size(self):
        if self.size is None and self.membertype_offsets is not None: # if explicit size not provided, calculate on our own
            offset, memtype = self.membertype_offsets[-1]
            self.size = offset + memtype.get_size()

    # by default, assume a primitive type (doesn't reference any other types)
    # override in children
    def is_primitive(self):
        return False

    # Is this type a complex type? -> References "sub-components"?
    # override in children
    def is_complex(self):
        return True

    def composition_level(self):
        return 1 + max([ memtype.composition_level() for _, memtype in self.membertype_offsets ])

    def get_membertype_offsets_with_padding(self):
        membertype_offsets = []
        n = self.get_number_members()
        for i in range(0, n):
            padding = 0
            offset, memtype = self.membertype_offsets[i]
            membertype_offsets.append((offset, memtype))

            # if this is the last member, check to see that offset + memtype.size == size
            if i == n - 1:
                padding = self.size - (offset + memtype.size)
            
            # otherwise...
            else:
                _offset, _ = self.membertype_offsets[i + 1]
                padding = _offset - (offset + memtype.size)

            if padding > 0:
                padding_offset = offset + memtype.size
                padding_dtype = DataTypeUndefined(size=padding)
                membertype_offsets.append((padding_offset, padding_dtype))

        return membertype_offsets


    def flatten(self):
        for (offset, memtype) in self.membertype_offsets:
            for (off, primitive) in memtype.flatten():
                yield (offset + off, primitive)

    # get the component type that starts at a given offset, possibly restricting size
    # the component could be padding (undefined type)
    # int -> DescentRecord | None
    def get_component_type_at_offset(self, offset, size=None):
        for _offset, memtype in self.get_membertype_offsets_with_padding():
            if _offset == offset:
                return DataTypeRecursiveDescent.DescentRecord(
                    DataTypeRecursiveDescent.Relationship.STRUCT_MEMBER,
                    offset,
                    memtype
                ) if size is None or size <= memtype.size else None
            
            if _offset > offset:
                break
        return None

    # get the component type that includes a given offset (could be padding)
    # return the actual offset the component type was found at
    # actual offset <= offset
    # int -> (int, DataType) | None
    def get_component_type_containing_offset(self, offset):
        for _offset, memtype in self.get_membertype_offsets_with_padding():
            if _offset <= offset < _offset + memtype.size:
                return DataTypeRecursiveDescent.DescentRecord(
                    DataTypeRecursiveDescent.Relationship.STRUCT_MEMBER,
                    _offset,
                    memtype
                )
        return None

    def members_equal(self, other):
        assert(other.metatype == self.metatype)
        return len(self.membertype_offsets) == len(other.membertype_offsets) \
            and all([
            (offset, memtype) == (_offset, _memtype) for
            (offset, memtype), (_offset, _memtype) in zip(self.membertype_offsets, other.membertype_offsets)
        ])

    def __eq__(self, other):
        return self.rough_match(other) and self.members_equal(other)

    def __str__(self):
        s = "<STRUCT "
        if self.name is not None:
            s += self.name + " "

        s += "membertypes={} ".format(len(self.get_membertypes()))
        s += "size={}>".format(self.size)

        return s

    def __hash__(self):
        return hash((self.metatype, self.size, tuple(self.membertype_offsets)))

class DataTypeUnion(DataType):
    """
    Datatype representing a C union type.
    """
    def __init__(self, name=None, membertypes=None, size=None):
        """
        membertypes: [DataType]
            The data types of that could possibly be instantiated in the union.
        """
        self.name = name
        self.membertypes = membertypes
        super(DataTypeUnion, self).__init__(
            metatype=MetaType.UNION,
            size=size
        )

    def _resolve_size(self):
        if self.size is None and self.membertypes is not None: # if explicit size not provided, calculate on our own
            self.size = max([ mem.get_size() for mem in self.membertypes ])

    # by default, assume a primitive type (doesn't reference any other types)
    # override in children
    def is_primitive(self):
        return False

    # Is this type a complex type? -> References "sub-components"?
    # override in children
    def is_complex(self):
        return True

    def composition_level(self):
        return 1 + max([ memtype.composition_level() for memtype in self.membertypes ])

    # union contains non-deterministic primitive decomposition
    # just return an "undefined" type equal to the size of the union
    def flatten(self):
        yield (0, DataTypeUndefined(size=self.size))

    # offset = the offset into this datatype to find match for
    # offset_to_subtype = the actual offset of the direct subtype in recursion
    # TODO: size parameter should be changed to 'match_dtype' so we can check type equality instead of just size
    def get_type_at_offset_recursive(self, offset, match_type=None, exact_match=False):
        # base case: offset == 0 and size matches (if size given)
        # return empty path since we didn't have to recurse at all
        if offset == 0 \
            and (match_type is None \
                or self == match_type \
                or (not exact_match and self.rough_match(match_type))
            ):
            return []

        # try to match on each member type iteratively
        # if one matches, then terminate
        # offset to all members is 0
        for memtype in self.membertypes:
            # recurse: [DescentNode]
            recurse = memtype.get_type_at_offset_recursive(offset, match_type=match_type, exact_match=exact_match)
            if recurse is not None:
                record = DataTypeRecursiveDescent.DescentRecord(
                    DataTypeRecursiveDescent.Relationship.UNION_MEMBER,
                    0, # offset to each member is 0
                    memtype
                )
                return [record] + recurse

        return None

    def members_equal(self, other):
        assert(other.metatype == self.metatype)
        return len(self.membertypes) == len(other.membertypes) \
            and all([
            memtype == _memtype for memtype, _memtype 
            in zip(self.membertypes, other.membertypes)
        ])

    def __eq__(self, other):
        return self.rough_match(other) and self.members_equal(other)

    def __str__(self):
        s = "<UNION "
        if self.name is not None:
            s += self.name + " "

        s += "membertypes={} ".format(len(self.membertypes))
        s += "size={}>".format(self.size)

        return s

    def __hash__(self):
        return hash((self.metatype, self.size, tuple(self.membertypes)))
