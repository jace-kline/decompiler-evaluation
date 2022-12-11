from __main__ import * # import all the implicit GhidraScript state & methods from the main script

from resolve import *
from resolve_stubs import *
from lang import *
from parse_ghidra_util import *
from ghidra.program.model.data import Array, Structure, Union, Enum, Pointer, TypeDef, FunctionDefinition, DefaultDataType, BuiltInDataType, BooleanDataType, CharDataType, AbstractIntegerDataType, AbstractFloatDataType, AbstractComplexDataType, AbstractStringDataType, Undefined, VoidDataType as _VoidDataType

def parse():
    parser = ParseGhidra()
    return parser.parse()

class ParseGhidraException(Exception):
    pass

class ParseGhidra(object):
    def __init__(self):
        self.curr = getCurrentProgram()
        self.monitor = getMonitor()
        self.dtype_manager = self.curr.getDataTypeManager()

        # utility class instantiation
        self.util = GhidraUtil(self.curr, self.monitor)

        # holds {ref: obj} mappings
        # obj is a Ghidra type (DataType, Variable, Address, etc)
        self.objmap = {}
        # holds {ref: stub} mappings
        self.db = ResolverDatabase()

    # This maps an object to a unique identifier for it.
    # We are using the address of the object, obtained via the id() function.
    def to_key(self, obj):
        return hash(obj)

    # place a ghidra object in the objmap
    # referenced by its Python object address
    def register_obj(self, obj):
        k = self.to_key(obj)
        if (not self.db.exists(k)) and (k not in self.objmap):
            self.objmap[k] = obj
        return k

    # Wrap a stub in a ResolverDatabase.ResolverRecord and insert into the DB.
    # Return the new key, which is the address of the stub.
    def make_stub(self, stub):
        key = self.to_key(stub)
        self.db.make_record(key, stub)
        return key

    # A utility for the parsing methods to ensure that the passed in ref (key)
    # exists in the internal object map.
    # Returns the object associated with the ref if valid.
    def follow_objmap_ref(self, ref):
        # try to lookup in objmap
        # if not found, raise error
        obj = self.objmap.get(ref, None)
        if obj is None:
            raise ParseGhidraException("Referenced object does not exist in map")
        return obj

    def parse(self):
        self.generate_proginfo_stub()
        proginfo = self.db.resolve_root()
        return proginfo

    def generate_proginfo_stub(self):
        # Register decompiled HighFunction objects
        functionrefs = [ self.register_obj(highfn) for highfn in self.util.get_decompiled_functions() ]

        # for each HighFunction, register the global HighSymbol objects referenced
        global_varinfos = self.util.get_global_vars()
        globalrefs = [ self.register_obj(varinfo) for varinfo in global_varinfos ]

        stub = ProgramInfoStub(
            globalrefs=globalrefs,
            functionrefs=functionrefs
        )

        ref = self.make_stub(stub)
        self.db.set_root_key(ref)

        for functionref in functionrefs:
            self.parse_highfunction(functionref)

        for globalref in globalrefs:
            self.parse_varinfo(globalref, param=False, functionref=None)

    # ref :: key to HighFunction object
    # create and store FunctionStub
    def parse_highfunction(self, ref):

        if self.db.exists(ref):
            return

        highfn = self.follow_objmap_ref(ref) # HighFunction
        fn = highfn.getFunction() # Function

        name = fn.getName() # str

        # get absolute addresses (as ints) of low and high PCs for function
        startpc, endpc = self.util.get_function_pc_range(fn) # (int, int)
        # translate the raw PC ints to Address objects
        startaddr = AbsoluteAddress(startpc)
        endaddr = AbsoluteAddress(endpc)

        params = self.util.get_highfn_params(highfn) # Iter<VariableInfo>
        paramrefs = [ self.register_obj(v) for v in params ]

        vars = self.util.get_highfn_local_vars(highfn) # Iter<VariableInfo>
        varrefs = [ self.register_obj(v) for v in vars ]

        fnproto = highfn.getFunctionPrototype()
        rettyperef = self.make_stub(DataTypeVoidStub()) if fnproto.hasNoReturn() else self.register_obj(fnproto.getReturnType())
        variadic = fnproto.isVarArg()

        stub = FunctionStub(
            name=name,
            startaddr=startaddr,
            endaddr=endaddr,
            rettyperef=rettyperef,
            paramrefs=paramrefs,
            varrefs=varrefs,
            variadic=variadic
        )

        # insert this record
        self.db.make_record(ref, stub)
        # self.make_stub(stub)

        # recurse on child components of this function
        for paramref in paramrefs:
            self.parse_varinfo(paramref, param=True, functionref=ref)

        for varref in varrefs:
            self.parse_varinfo(varref, param=False, functionref=ref)

        self.parse_datatype(rettyperef)

    # ref to a VariableInfo object that refers to a variable/parameter
    def parse_varinfo(self, ref, param=False, functionref=None):
        if self.db.exists(ref):
            return

        varinfo = self.follow_objmap_ref(ref)

        name = varinfo.getName()

        dtype = varinfo.getDataType()
        dtyperef = self.register_obj(dtype)

        # get the liveranges for the variable
        liveranges = self.get_varinfo_liveranges(varinfo, functionref=functionref)

        stub = VariableStub(
            name=name,
            dtyperef=dtyperef,
            liveranges=liveranges,
            param=param,
            functionref=functionref
        )

        self.db.make_record(ref, stub)

        # recurse on sub components
        self.parse_datatype(dtyperef)

    # ref to a Ghidra DataType object
    def parse_datatype(self, ref):
        # if this ref is already in the db, do nothing
        if self.db.exists(ref):
            return

        dtype = self.follow_objmap_ref(ref)

        # extract the metatype & size from the dtype
        metatype = ParseGhidra.datatype2metatype(dtype)
        size = 0 if dtype.isZeroLength() else dtype.getLength()

        # we want to create a stub & recursively capture sub-types to resolve
        stub = None
        subtyperefs = []
        basetype = None

        # switch on the metatype & generate correct stub
        # possibly recursive if complex data type
        if metatype == MetaType.INT:
            signed = dtype.isSigned()

            stub = DataTypeIntStub(
                size=size,
                signed=signed
            )

        elif metatype == MetaType.FLOAT:
            stub = DataTypeFloatStub(
                size=size
            )

        elif metatype == MetaType.POINTER:
            basetype = dtype.getDataType()
            basetyperef = self.register_obj(basetype) \
                if basetype is not None \
                else self.make_stub(DataTypeVoidStub())

            stub = DataTypePointerStub(
                basetyperef=basetyperef,
                size=size
            )
            subtyperefs.append(basetyperef)

        elif metatype == MetaType.ARRAY:
            basetype = dtype.getDataType()
            length = dtype.getNumElements()

            # while basetyperef is an array type, add more dimensions to the top-level array
            dimensions = [length]
            while ParseGhidra.datatype2metatype(basetype) == MetaType.ARRAY:
                dim = basetype.getNumElements()
                dimensions.append(dim)
                basetype = basetype.getDataType()

            # fall through... the basetype is no longer an array type
            basetyperef = self.register_obj(basetype)

            stub = DataTypeArrayStub(
                basetyperef=basetyperef,
                dimensions=tuple(dimensions)
            )
            subtyperefs.append(basetyperef)

        elif metatype == MetaType.STRUCT:
            name = dtype.getName()
            # membertype_offsets = ( (mem.getOffset(), mem.getDataType()) for mem in dtype.getComponents() )
            # membertyperef_offsets = [ (offset, self.register_obj(memtype)) for offset, memtype in membertype_offsets ]
            membertyperef_offsets = []
            for mem in dtype.getComponents():
                offset = mem.getOffset()
                _dtype = mem.getDataType()
                _dtype_size = _dtype.getLength()
                _dtype_metatype = ParseGhidra.datatype2metatype(_dtype)
                key = self.to_key(_dtype)

                # if the member points back to same struct type...
                if key == ref:
                    ptrstub = DataTypePointerStub(
                        basetyperef=ref,
                        size=_dtype_size
                    )
                    key = self.make_stub(ptrstub)
                    self.objmap[key] = 1
                    membertyperef_offsets.append((offset, key))

                # if undefined member of size 1, assume a padding byte -> skip
                elif _dtype_metatype == MetaType.UNDEFINED and _dtype_size == 1:
                    pass
                
                # otherwise, register the member datatype
                else:
                    key = self.register_obj(_dtype)
                    subtyperefs.append(key)
                    membertyperef_offsets.append((offset, key))

            stub = DataTypeStructStub(
                name=name,
                membertyperef_offsets=membertyperef_offsets,
                size=size
            )
            # subtyperefs += [ ref for _, ref in membertyperef_offsets ]

        elif metatype == MetaType.UNION:
            name = dtype.getName()
            # membertypes = ( mem.getDataType() for mem in dtype.getComponents() )
            # membertyperefs = [ self.register_obj(memtype) for memtype in membertypes ]

            membertyperefs = []
            for mem in dtype.getComponents():
                _dtype = mem.getDataType()
                key = self.to_key(_dtype)

                # if the member points back to same struct type...
                if key == ref:
                    ptrstub = DataTypePointerStub(
                        basetyperef=ref,
                        size=_dtype.getLength()
                    )
                    key = self.make_stub(ptrstub)
                    self.objmap[key] = 1
                else:
                    key = self.register_obj(_dtype)
                    subtyperefs.append(key)
                
                membertyperefs.append(key)

            stub = DataTypeUnionStub(
                name=name,
                membertyperefs=membertyperefs,
                size=size
            )
            subtyperefs += membertyperefs

        elif metatype == MetaType.UNDEFINED:
            stub = DataTypeUndefinedStub(size=size)

        elif metatype == MetaType.VOID:
            stub = DataTypeVoidStub()

        elif metatype == MetaType.FUNCTION_PROTOTYPE:
            rettype = dtype.getReturnType()
            rettyperef = self.register_obj(rettype)

            variadic = dtype.hasVarArgs()
            paramdefs = dtype.getArguments() # [ParameterDefinition]
            paramtypes = [ paramdef.getDataType() for paramdef in paramdefs ]
            paramtyperefs = [ self.register_obj(paramtype) for paramtype in paramtypes ]

            stub = DataTypeFunctionPrototypeStub(
                rettyperef=rettyperef,
                paramtyperefs=paramtyperefs,
                variadic=variadic
            )
            subtyperefs += paramtyperefs

        elif metatype == MetaType.TYPEDEF:
            name = dtype.getName()
            basetype = dtype.getDataType()
            basetyperef = self.register_obj(basetype)

            stub = DataTypeTypedefStub(
                name=name,
                basetyperef=basetyperef
            )
            subtyperefs.append(basetyperef)

        elif metatype == MetaType.ENUM:
            # create and add stub for the underlying integer type
            basetyperef = self.make_stub(DataTypeIntStub(size=size, signed=True))
            self.objmap[basetyperef] = 1

            stub = DataTypeEnumStub(basetyperef=basetyperef)

        elif metatype == MetaType.STRING:
            # convert "strings" to char array
            basetyperef = self.make_stub(DataTypeIntStub(size=1, signed=True))
            self.objmap[basetyperef] = 1
            dimensions = (dtype.getLength(),)

            stub = DataTypeArrayStub(
                basetyperef=basetyperef,
                dimensions=dimensions
            )

        else:
            raise NotImplementedError("MetaType code does not exist")

        # insert this stub into DB
        self.db.make_record(ref, stub)

        # Recurse on sub-refs
        for subtyperef in subtyperefs:
            self.parse_datatype(subtyperef)

    # Convert a Ghidra-represented Address into our Address representation
    # Address (Ghidra) -> Address (our language)
    def get_address(self, addr):
        # ensure valid Ghidra Address object
        if not self.util.is_valid_address(addr):
            return None

        addrtype = ParseGhidra.addr2addrtype(addr)
        offset = addr.getOffset()

        if addrtype == AddressType.STACK:
            return StackAddress(self.util.resolve_stack_frame_offset(offset))
        elif addrtype == AddressType.ABSOLUTE:
            return AbsoluteAddress(self.util.resolve_absolute_address(offset))
        elif addrtype == AddressType.EXTERNAL:
            return ExternalAddress()
        elif addrtype == AddressType.REGISTER:
            regnum = self.util.ghidra2dwarf_register(offset)
            # TODO: what if regnum is None?
            return RegisterAddress(regnum)
        elif addrtype == AddressType.UNKNOWN:
            return UnknownAddress()
        else:
            raise ParseGhidraException("No address translation found")

    # Given a HighSymbol, extract the VariableStorage object and translate into LiveRangeAddress objects.
    # local indicates whether or not this given HighSymbol should be considered a "local variable" for the purposes of extracting its parent function.
    # (VariableInfo, ref?) -> [AddressLiveRange]
    def get_varinfo_liveranges(self, varinfo, functionref=None):
        # Should we keep the given range in the liveranges list?
        # Valid range should be non-null, have a non-null & known address
        # (AddressLiveRange | None) -> bool
        def valid_range(rng):
            return rng is not None and rng.addr is not None and rng.addr.addrtype != AddressType.UNKNOWN

        local = functionref is not None
        storage = varinfo.getStorage()
        varnodes = storage.getVarnodes()
        highfn = self.follow_objmap_ref(functionref) if functionref is not None else None
        liveranges = (
            self.get_varnode_liverange(varnode, highfn=highfn)
            for varnode in varnodes
        )
        return [ rng for rng in liveranges if valid_range(rng) ]

    # Returns an AddressLiveRange object for a given Varnode (SSA variable), or returns None if no location info available.
    # (Varnode, HighFunction?) -> AddressLiveRange | None
    def get_varnode_liverange(self, varnode, highfn=None):
        local = highfn is not None
        addr = self.get_address(varnode.getAddress()) # Address

        fnstart = fnend = None
        if highfn:
            fnstart, fnend = self.util.get_function_pc_range(highfn.getFunction())

        startpc = endpc = None
        rng = self.util.get_varnode_pc_range(varnode)
        if rng is not None:
            startpc, endpc = rng

        # If this doesn't have a getPCAddress(), then assume its a parameter.
        # If parameter, take the start address to be that of the start of the parent function.
        startpc = startpc if startpc is not None else fnstart
        endpc = endpc if endpc is not None else fnend

        # TODO: what if startpc is not None and endpc is None?

        # fail if there is...
        # no address OR it is a local variable and there are missing PC bounds
        if addr is None or (local and (not startpc or not endpc)):
            return None

        return AddressLiveRange(
            addr=addr,
            startpc=AbsoluteAddress(startpc) if startpc else None,
            endpc=AbsoluteAddress(endpc) if endpc else None
        )

    # Given a Ghidra DataType object, map it to the metatype code in our translation language.
    @staticmethod
    def datatype2metatype(dtype):
        # interface / complex types
        if isinstance(dtype, Array):
            return MetaType.ARRAY
        elif isinstance(dtype, Structure):
            return MetaType.STRUCT
        elif isinstance(dtype, Union):
            return MetaType.UNION
        elif isinstance(dtype, Enum):
            return MetaType.ENUM
        elif isinstance(dtype, Pointer):
            return MetaType.POINTER
        elif isinstance(dtype, TypeDef):
            return MetaType.TYPEDEF
        elif isinstance(dtype, FunctionDefinition):
            return MetaType.FUNCTION_PROTOTYPE

        # base types
        elif isinstance(dtype, AbstractComplexDataType):
            raise NotImplementedError()
        elif isinstance(dtype, AbstractFloatDataType):
            return MetaType.FLOAT
        elif isinstance(dtype, AbstractIntegerDataType):
            return MetaType.INT
        elif isinstance(dtype, AbstractStringDataType):
            return MetaType.STRING
        elif isinstance(dtype, _VoidDataType):
            return MetaType.VOID
        else:
            return MetaType.UNDEFINED

    # Given a Ghidra Address object, produce an AddressSpace enum int in our own representation
    @staticmethod
    def addr2addrtype(addr):
        addrspace = addr.getAddressSpace()
        if addrspace.isStackSpace():
            return AddressType.STACK
        elif addrspace.isMemorySpace():
            return AddressType.ABSOLUTE
        elif addrspace.isExternalSpace():
            return AddressType.EXTERNAL
        elif addrspace.isRegisterSpace():
            return AddressType.REGISTER
        else:
            return AddressType.UNKNOWN



