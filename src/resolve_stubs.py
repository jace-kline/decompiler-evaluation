from lang import *
from resolve import *

# Each "stub" is a flattened version of a desired data structure
# in our target language. It is assumed that each stub object is
# stored within a "ResolverRecord" object within a "ResolverDatabase".
# Every record (& therefore stub) is uniquely identified by a key in the database.
# We ultimately want to create a nested/recursive structure from the stubs. 

# filter a list of variables during resolution...
# a 0-sized variable should not exist
def filter_variables(vars):
    def cond(var):
        return not var.get_size() == 0 and not var.get_size() is None
    
    return [ var for var in vars if cond(var) ]

# eliminate the aliasing redirections
def db_resolve_subtype_ref(db, ref):
    ALIAS_TYPES = (DataTypeQualifierStub, DataTypeTypedefStub, DataTypeEnumStub)
    curref = ref
    ref_record = db.lookup(curref)
    while isinstance(ref_record.stub, ALIAS_TYPES):
        curref = ref_record.stub.basetyperef
        ref_record = db.lookup(curref)
    return curref

def db_resolve_subtype(db, ref):
    return db.resolve(db_resolve_subtype_ref(db, ref))

def db_resolve_subtypes(db, refs):
    return [ db_resolve_subtype(db, ref) for ref in refs ]

# This is the root node of the translation.
# It references all global variables and functions for a target program.
class ProgramInfoStub(ResolverDatabase.ResolverStub):
    def __init__(self, globalrefs=[], functionrefs=[]):
        self.globalrefs = globalrefs
        self.functionrefs = functionrefs

    def resolve(self, record):
        record.obj = ProgramInfo()

        globals = record.db.resolve_many(self.globalrefs)
        functions = record.db.resolve_many(self.functionrefs)

        record.obj.globals = filter_variables(globals)
        record.obj.functions = functions
        return record.obj

    def __str__(self):
        return "<ProgramInfoStub globalrefs={} functionrefs={}>".format(self.globalrefs, self.functionrefs)

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash((tuple(self.globalrefs), tuple(self.functionrefs)))

class FunctionStub(ResolverDatabase.ResolverStub):
    def __init__(self, name=None, startaddr=None, endaddr=None, rettyperef=None, paramrefs=[], varrefs=[], variadic=False):
        self.name = name
        self.startaddr = startaddr
        self.endaddr = endaddr
        self.rettyperef = rettyperef
        self.paramrefs = paramrefs
        self.varrefs = varrefs
        self.variadic = variadic

    def resolve(self, record):
        assert_not_none(self, "paramrefs")
        assert_not_none(self, "varrefs")

        record.obj = Function()

        # startaddr = record.db.resolve(self.startaddrref)
        rettype = DataTypeVoid() if self.rettyperef is None else db_resolve_subtype(record.db, self.rettyperef)
        params = record.db.resolve_many(self.paramrefs)
        vars = record.db.resolve_many(self.varrefs)

        record.obj.name = self.name
        record.obj.startaddr = self.startaddr
        record.obj.endaddr = self.endaddr
        record.obj.rettype = rettype
        record.obj.params = filter_variables(params)
        record.obj.vars = filter_variables(vars)
        record.obj.variadic = self.variadic
        return record.obj

    def __str__(self):
        return "<FunctionStub paramrefs={} varrefs={}>".format(self.paramrefs, self.varrefs)

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash((self.name, self.startaddr, self.endaddr, self.rettyperef, tuple(self.paramrefs), tuple(self.varrefs), self.variadic))

class VariableStub(ResolverDatabase.ResolverStub):
    def __init__(self, name=None, dtyperef=None, liveranges=[], param=False, functionref=None):
        self.name = name
        self.dtyperef = dtyperef
        self.liveranges = liveranges
        self.param = param
        self.functionref = functionref

    def resolve(self, record):
        assert_not_none(self, "dtyperef")
        assert_not_none(self, "liveranges")

        record.obj = Variable()

        function = None
        if self.functionref is not None:
            function = record.db.resolve(self.functionref)

        dtype = db_resolve_subtype(record.db, self.dtyperef)

        record.obj.name = self.name
        record.obj.dtype = dtype
        record.obj.liveranges = self.liveranges
        record.obj.param = self.param
        record.obj.function = function
        return record.obj

    def __str__(self):
        return "<VariableStub dtyperef={} functionref={}>".format(self.dtyperef, self.functionref)

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash((self.name, self.dtyperef, tuple(self.liveranges), self.param))

class DataTypeStub(ResolverDatabase.ResolverStub):
    def __init__(self, metatype=MetaType.VOID, size=None):
        self.metatype = metatype
        self.size = size

    def __hash__(self):
        return hash((self.metatype, self.size))

class DataTypeFunctionPrototypeStub(DataTypeStub):
    def __init__(self, rettyperef=None, paramtyperefs=[], variadic=False):
        super(DataTypeFunctionPrototypeStub, self).__init__(
            metatype=MetaType.FUNCTION_PROTOTYPE,
            size=0
        )
        self.rettyperef = rettyperef
        self.paramtyperefs = paramtyperefs
        self.variadic = variadic

    def resolve(self, record):

        record.obj = DataTypeFunctionPrototype()

        # if rettype is None, assume void return type
        rettype = DataTypeVoid() if self.rettyperef is None else record.db.resolve(self.rettyperef)
        paramtypes = db_resolve_subtypes(record.db, self.paramtyperefs)

        record.obj.rettype = rettype
        record.obj.paramtypes = paramtypes
        record.obj.variadic = self.variadic
        return record.obj

    def __str__(self):
        return "<DataTypeFunctionPrototypeStub rettyperef={} paramtyperefs={}>".format(self.rettyperef, self.paramtyperefs)

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash((self.metatype, self.size, self.rettyperef, tuple(self.paramtyperefs), self.variadic))

class DataTypeIntStub(DataTypeStub):
    def __init__(self, size=None, signed=True):
        super(DataTypeIntStub, self).__init__(
            metatype=MetaType.INT,
            size=size
        )
        self.signed = signed

    def resolve(self, record):
        assert_not_none(self, "size")

        return DataTypeInt(size=self.size, signed=self.signed)

    def __hash__(self):
        return hash((self.metatype, self.size, self.signed))

class DataTypeFloatStub(DataTypeStub):
    def __init__(self, size=None):
        super(DataTypeFloatStub, self).__init__(
            metatype=MetaType.FLOAT,
            size=size
        )

    def resolve(self, record):
        assert_not_none(self, "size")

        return DataTypeFloat(size=self.size)

class DataTypeUndefinedStub(DataTypeStub):
    def __init__(self, size=None):
        super(DataTypeUndefinedStub, self).__init__(
            metatype=MetaType.UNDEFINED,
            size=size
        )

    def resolve(self, record):
        assert_not_none(self, "size")

        return DataTypeUndefined(size=self.size)

class DataTypeVoidStub(DataTypeStub):
    def __init__(self):
        super(DataTypeVoidStub, self).__init__(
            metatype=MetaType.VOID,
            size=0
        )

    def resolve(self, record):
        return DataTypeVoid()

class DataTypePointerStub(DataTypeStub):
    def __init__(self, basetyperef=None, size=None):
        super(DataTypePointerStub, self).__init__(
            metatype=MetaType.POINTER,
            size=size
        )
        self.basetyperef = basetyperef

    def resolve(self, record):
        assert_not_none(self, "basetyperef")
        assert_not_none(self, "size")

        record.obj = DataTypePointer(
            basetype=None,
            size=self.size
        )

        basetype = db_resolve_subtype(record.db, self.basetyperef)
        # if basetype is None:
        #     print(self.basetyperef)
        #     refrecord = record.db.lookup(self.basetyperef)
        #     print(refrecord)
        #     raise Exception("Pointer basetype is None")

        record.obj.basetype = basetype
        return record.obj

    def __str__(self):
        return "<DataTypePointerStub basetyperef={}>".format(self.basetyperef)

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash((self.metatype, self.size, self.basetyperef))

class DataTypeArrayStub(DataTypeStub):
    def __init__(self, basetyperef=None, dimensions=None):
        super(DataTypeArrayStub, self).__init__(
            metatype=MetaType.ARRAY,
            size=None
        )
        self.basetyperef = basetyperef
        self.dimensions = dimensions

    def resolve(self, record):
        assert_not_none(self, "basetyperef")
        assert_not_none(self, "dimensions")

        record.obj = DataTypeArray()

        basetype = db_resolve_subtype(record.db, self.basetyperef)
        if basetype is None:
            print(self.basetyperef)
            basetyperef = self.basetyperef
            while True:
                try:
                    refrecord = record.db.lookup(basetyperef)
                    print(refrecord)
                    basetyperef = refrecord.stub.basetyperef
                except:
                    break
            subtyperef = db_resolve_subtype_ref(record.db, self.basetyperef)
            print(subtyperef)
            print(record.db.lookup(subtyperef))
            print(record.db.resolve(subtyperef))
            raise Exception("Array basetype is None")
        if self.size is None:
            self.size = DataTypeArray.compute_size(self.dimensions, basetype.size)

        record.obj.basetype = basetype
        record.obj.dimensions = self.dimensions
        record.obj.size = self.size
        return record.obj

    def __str__(self):
        return "<DataTypeArrayStub basetyperef={}>".format(self.basetyperef)

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash((self.metatype, self.size, self.basetyperef, self.dimensions))

class DataTypeStructStub(DataTypeStub):
    def __init__(self, name="", membertyperef_offsets=[], size=None):
        super(DataTypeStructStub, self).__init__(
            metatype=MetaType.STRUCT,
            size=size
        )
        self.name = name
        # list of (offset, membertype ref) pairs
        self.membertyperef_offsets=membertyperef_offsets

    def resolve(self, record):
        offsets = [ offset for offset, _ in self.membertyperef_offsets ]
        membertyperefs = [ ref for _, ref in self.membertyperef_offsets ]

        record.obj = DataTypeStruct()
        membertypes = db_resolve_subtypes(record.db, membertyperefs)
        membertype_offsets = list(zip(offsets, membertypes))

        if self.size is None:
            if not membertype_offsets:
                # if (offset, membertype) pairs list is empty, size = 0
                self.size = 0
            else:
                # get last member's offset, then add then size of that member's type
                offset, memtype = membertype_offsets[-1]
                size = offset + memtype.get_size()
                end_padding = size % DataTypeStruct.ALIGN_SIZE
                self.size = size + end_padding

        # correct the fields after recursion occurs
        record.obj.name = self.name
        record.obj.membertype_offsets = membertype_offsets
        record.obj.size = self.size
        return record.obj

    def __str__(self):
        return "<DataTypeStructStub membertyperefs={}>".format([ ref for _, ref in self.membertyperef_offsets ])

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash((self.metatype, self.size, tuple(self.membertyperef_offsets)))

class DataTypeUnionStub(DataTypeStub):
    def __init__(self, name="", membertyperefs=[], size=None):
        super(DataTypeUnionStub, self).__init__(
            metatype=MetaType.UNION,
            size=size
        )
        self.name = name
        self.membertyperefs=membertyperefs

    def resolve(self, record):
        record.obj = DataTypeUnion()
        membertypes = db_resolve_subtypes(record.db, self.membertyperefs)

        if self.size is None:
            self.size = max([ subtype.size for subtype in membertypes ])

        # correct the fields after recursion occurs
        record.obj.name = self.name
        record.obj.membertypes = membertypes
        record.obj.size = self.size
        return record.obj

    def __str__(self):
        return "<DataTypeUnionStub membertyperefs={}>".format(self.membertyperefs)

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash((self.metatype, self.size, tuple(self.membertyperefs)))

class DataTypeTypedefStub(DataTypeStub):
    def __init__(self, name="", basetyperef=None):
        super(DataTypeTypedefStub, self).__init__(
            metatype=MetaType.TYPEDEF
        )
        self.basetyperef = basetyperef
        self.name = name

    def resolve(self, record):
        # for typedefs, no reference => void alias
        record.obj = record.db.resolve(self.basetyperef)
        return record.obj

    def __str__(self):
        return "<DataTypeTypedefStub basetyperef={}>".format(self.basetyperef)

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash((self.metatype, self.size, self.basetyperef))
        
class DataTypeEnumStub(DataTypeStub):
    def __init__(self, basetyperef):
        super(DataTypeEnumStub, self).__init__(
            metatype=MetaType.ENUM
        )
        self.basetyperef = basetyperef

    def resolve(self, record):
        assert_not_none(self, "basetyperef")
        
        # directly return the aliased type
        record.obj = record.db.resolve(self.basetyperef)
        return record.obj

    def __str__(self):
        return "<DataTypeEnumStub basetyperef={}>".format(self.basetyperef)

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash((self.metatype, self.size, self.basetyperef))


class DataTypeQualifierStub(DataTypeStub):
    def __init__(self, basetyperef=None):
        super(DataTypeQualifierStub, self).__init__(
            metatype=MetaType.QUALIFIER
        )
        self.basetyperef = basetyperef

    def resolve(self, record):
        assert_not_none(self, "basetyperef")
        
        # directly return the aliased type
        record.obj = record.db.resolve(self.basetyperef)
        return record.obj

    def __str__(self):
        return "<DataTypeQualifierStub basetyperef={}>".format(self.basetyperef)

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash((self.metatype, self.size, self.basetyperef))

