import sys
import random
from elftools.dwarf.constants import *
from resolve import *
from resolve_stubs import *
from parse_dwarf_util import *

class ParseDWARFException(Exception):
    pass

class ParseDWARF(object):
    # DB keys are of the form (CU offset, DIE offset).
    # CU offset = -1 implies a custom added element.

    def __init__(self, dwarfinfo):
        self.dwarfinfo = dwarfinfo
        # holds {(CU offset, DIE offset) -> DIE} mappings
        self.diemap = {}
        # holds {(CU offset, DIE offset) -> record} mappings
        self.db = ResolverDatabase()

        # holds the static local variables (that should be treated as globals)
        self.static_local_refs = []

    def get_DIE_key(self, die):
        if die is None:
            return None
        return (die.cu.cu_offset, die.offset)

    def _fill_diemap(self):
        self.diemap = dict([(self.get_DIE_key(die), die) for die in get_all_DIEs(self.dwarfinfo)])

    def generate_unique_key(self):
        while True:
            key = (-1, random.randint(0, 999999999)) # -1 CU indicates we added it
            if key not in self.diemap and not self.db.exists(key):
                break
        return key

    # Generate a key for the stub, then insert into the DB as a record.
    # Return the new key created.
    def make_stub(self, stub):
        key = self.generate_unique_key()
        self.db.make_record(key, stub)
        return key

    # For a given ref in the diemap, recursively generate the associated stub(s)
    # and add to the resolver database.
    # Returns nothing, only updates the internal DB.
    # ref = (CU offset, DIE offset)
    def generate_DIE_stubs(self, ref):
        if self.db.exists(ref):
            return

        die = self.diemap.get(ref, None)
        if die is None:
            raise ParseDWARFException(
                "Attempted to reference unknown key {}"
                .format(ref)
            )

        subrefs = []
        stub = None

        # Function-like DIE
        if die.tag == "DW_TAG_subprogram":
            name = get_DIE_name_follow_abstract_origin(die)

            pc_range = get_DIE_low_high_pc(die)
            # if could not extract PC range for function DIE, must be inlined
            startaddr = endaddr = None
            if pc_range is not None:
                lowpc, highpc = pc_range
                startaddr = AbsoluteAddress(lowpc)
                endaddr = AbsoluteAddress(highpc)

            # get basetype ref
            rettyperef = self.get_DIE_key(get_DIE_attr_ref_DIE(die, "DW_AT_type"))
            # if basetype ref is None, generate a VoidDataTypeStub in the DB to point to
            if rettyperef is None:
                rettyperef = self.make_stub(DataTypeVoidStub())
            
            def valid_die(die):
                return not is_artificial_DIE(die)    

            # get the parameter and variable children DIEs
            # only keep if the variable is associated with location(s) in the binary
            paramdies, vardies = get_param_var_DIEs(die)
            paramrefs = [ self.get_DIE_key(die) for die in paramdies if valid_die(die) ]
            varrefs = [ self.get_DIE_key(die) for die in vardies if valid_die(die) ]

            # does the function have a variable number of parameters?
            variadic = is_variadic_function_DIE(die)

            stub = FunctionStub(
                    name=name,
                    startaddr=startaddr,
                    endaddr=endaddr,
                    rettyperef=rettyperef,
                    paramrefs=paramrefs,
                    varrefs=varrefs,
                    variadic=variadic
                )

            subrefs += paramrefs + varrefs + [rettyperef]

        elif die.tag in ["DW_TAG_variable", "DW_TAG_formal_parameter"]:

            # try to extract the high-level variable name
            name = get_DIE_name_follow_abstract_origin(die)

            param = die.tag == "DW_TAG_formal_parameter" and not DIE_has_attr(die, "DW_AT_abstract_origin")

            # get the data type reference
            dtyperef = self.get_DIE_key(get_DIE_attr_ref_DIE_follow(die, "DW_AT_type"))
            assert(dtyperef is not None)

            # get the parent function ref in the database
            parentdie = get_DIE_parent_function_DIE(die)
            functionref = self.get_DIE_key(parentdie) if parentdie is not None else None

            # get the PC ranges for the most immediate parent scope of this variable
            pc_ranges = get_DIE_parent_scope_pc_ranges(die)
            scopestartpc = scopeendpc = None
            if pc_ranges is not None and len(pc_ranges) > 0:
                # we consider the default PC range for this variable to be
                # lowest addr from scope's ranges -> highest addr from scope's ranges
                _scopestartpc, _scopeendpc = merge_ranges(pc_ranges)
                scopestartpc = AbsoluteAddress(_scopestartpc)
                scopeendpc = AbsoluteAddress(_scopeendpc)

            liveranges = get_DIE_liveranges(
                die,
                scopestartpc=scopestartpc,
                scopeendpc=scopeendpc
            )

            is_static_local = functionref is not None \
                and liveranges \
                and liveranges[0].get_addr().get_addrtype() == AddressType.ABSOLUTE

            if is_static_local:
                self.static_local_refs.append(ref)

            # assert(len(liveranges) > 0) # if the high-level variable DIE has no location info, then it is not actualized in the assembly code

            stub = VariableStub(
                    name=name,
                    dtyperef=dtyperef,
                    liveranges=liveranges,
                    param=param,
                    functionref=functionref
                )

            subrefs.append(dtyperef)

        # if base type, lookup mapping
        elif die.tag == "DW_TAG_base_type":
            # get type's encoding and size
            enc = get_DIE_attr_value(die, "DW_AT_encoding")
            size = get_DIE_attr_value(die, "DW_AT_byte_size")
            
            # void
            if enc == DW_ATE_void:
                self.db.make_record(ref, DataTypeVoidStub())

            # pointer
            elif enc == DW_ATE_address:
                # get basetype ref
                basetyperef = self.get_DIE_key(get_DIE_attr_ref_DIE(die, "DW_AT_type"))
                # if basetype ref is None, generate a VoidDataTypeStub in the DB to point to
                if basetyperef is None:
                    basetyperef = self.make_stub(DataTypeVoidStub())

                stub = DataTypePointerStub(basetyperef=basetyperef, size=size)
                subrefs.append(basetyperef)
                
            # int/char (signed)
            elif enc in [DW_ATE_signed, DW_ATE_signed_char, DW_ATE_signed_fixed]:
                stub = DataTypeIntStub(size=size, signed=True)
            
            # int/char (unsigned)
            # regard bool as unsigned char
            # regard ASCII char as unsigned char
            elif enc in [DW_ATE_unsigned, DW_ATE_unsigned_char, DW_ATE_unsigned_fixed, DW_ATE_boolean, DW_ATE_ASCII]:
                stub = DataTypeIntStub(size=size, signed=False)

            # float
            elif enc in [DW_ATE_complex_float, DW_ATE_float, DW_ATE_decimal_float, DW_ATE_imaginary_float]:
                stub = DataTypeFloatStub(size=size)

            # anything else?
            else:
                stub = DataTypeUndefinedStub(size=size)

        # qualified types -> treat as their base types
        elif die.tag in ["DW_TAG_atomic_type", "DW_TAG_const_type", "DW_TAG_volatile_type", "DW_TAG_restrict_type"]:
            # get basetype ref
            basetyperef = self.get_DIE_key(get_DIE_attr_ref_DIE(die, "DW_AT_type"))
            # if basetype ref is None, generate a VoidDataTypeStub in the DB to point to
            if basetyperef is None:
                basetyperef = self.make_stub(DataTypeVoidStub())
            stub = DataTypeQualifierStub(basetyperef=basetyperef)
            subrefs.append(basetyperef)

        # pointer type
        elif die.tag == "DW_TAG_pointer_type":
            size = get_DIE_attr_value(die, "DW_AT_byte_size")
            basetyperef = self.get_DIE_key(get_DIE_attr_ref_DIE(die, "DW_AT_type"))
            # if basetype ref is None, generate a VoidDataTypeStub in the DB to point to
            if basetyperef is None:
                basetyperef = self.make_stub(DataTypeVoidStub())

            # set unresolved pointer
            stub = DataTypePointerStub(basetyperef=basetyperef, size=size)
            subrefs.append(basetyperef)

        # array type
        elif die.tag == "DW_TAG_array_type":
            # get the child subrange DIE object -> specifies the
            # bounds of the array
            rangedies = [ die for die in die.iter_children() if die.tag == "DW_TAG_subrange_type" ]

            def dim(rangedie):
                upbound = rangedie.attributes.get("DW_AT_upper_bound", 0)
                if upbound != 0:
                    return upbound.value + 1
                
                length = rangedie.attributes.get("DW_AT_count", 0)
                if length != 0:
                    return length.value

                return 0

            dimensions = tuple([ dim(subrange) for subrange in rangedies ])
            
            basetyperef = self.get_DIE_key(get_DIE_attr_ref_DIE(die, "DW_AT_type"))

            assert(len(dimensions) > 0)
            assert(basetyperef is not None)

            stub = DataTypeArrayStub(
                    basetyperef=basetyperef,
                    dimensions=dimensions
                )
            subrefs.append(basetyperef)

        # struct type
        elif die.tag == "DW_TAG_structure_type":
            memberdies = [ die for die in die.iter_children() if die.tag == "DW_TAG_member" ]

            # returns (offset, membertype ref) for each struct member
            membertyperef_offsets = [
                (
                    get_DIE_attr_value(die, "DW_AT_data_member_location"),
                    self.get_DIE_key(get_DIE_attr_ref_DIE(die, "DW_AT_type"))
                )
                for die in memberdies
            ]
            name = get_DIE_name(die)
            size = get_DIE_attr_value(die, "DW_AT_byte_size")

            stub = DataTypeStructStub(
                    name=name,
                    membertyperef_offsets=membertyperef_offsets,
                    size=size
                )

            subrefs += [ ref for _, ref in membertyperef_offsets ]

        # union type
        elif die.tag == "DW_TAG_union_type":
            
            membertyperefs = [ self.get_DIE_key(get_DIE_attr_ref_DIE(die, "DW_AT_type")) for die in die.iter_children() if die.tag == "DW_TAG_member" ]
            name = get_DIE_name(die)
            size = get_DIE_attr_value(die, "DW_AT_byte_size")

            stub = DataTypeUnionStub(
                    name=name,
                    membertyperefs=membertyperefs,
                    size=size
                )

            subrefs += membertyperefs

        # typedef
        elif die.tag == "DW_TAG_typedef":
            basetyperef = self.get_DIE_key(get_DIE_attr_ref_DIE(die, "DW_AT_type"))
            if basetyperef is None:
                basetyperef = self.make_stub(DataTypeVoidStub())
            name = get_DIE_name(die)

            stub = DataTypeTypedefStub(
                    name=name,
                    basetyperef=basetyperef
                )
            
            subrefs.append(basetyperef)

        # function prototype
        elif die.tag == "DW_TAG_subroutine_type":

            # if no ref, assume void return type
            rettyperef = self.get_DIE_key(get_DIE_attr_ref_DIE(die, "DW_AT_type"))
            if rettyperef is None:
                rettyperef = self.make_stub(DataTypeVoidStub())

            paramtyperefs = []
            variadic = False
            for childdie in die.iter_children():
                if childdie.tag == "DW_TAG_formal_parameter":
                    typeref = self.get_DIE_key(get_DIE_attr_ref_DIE(childdie, "DW_AT_type"))
                    paramtyperefs.append(typeref)
                elif childdie.tag == "DW_TAG_unspecifed_parameters":
                    variadic = True
                    break
            
            stub = DataTypeFunctionPrototypeStub(
                    rettyperef=rettyperef,
                    paramtyperefs=paramtyperefs,
                    variadic=variadic
                )
            
            subrefs += paramtyperefs + [rettyperef]

        # enum
        elif die.tag == "DW_TAG_enumeration_type":
            # get basetype ref
            basetyperef = self.get_DIE_key(get_DIE_attr_ref_DIE(die, "DW_AT_type"))
            # assert(basetyperef is not None)
            # if basetype ref is None, generate a VoidDataTypeStub in the DB to point to
            if basetyperef is None:
                basetyperef = self.make_stub(DataTypeVoidStub())
            stub = DataTypeEnumStub(basetyperef=basetyperef)
            subrefs.append(basetyperef)
            
        # other cases?
        else:
            raise NotImplementedError(die.tag)

        # Now that we have constructed the stub,
        # add corresponding record to the database
        self.db.make_record(ref, stub)

        # Recurse on sub-references
        for subref in subrefs:
            self.generate_DIE_stubs(subref)


    def parse(self):
        # collect DIEs and their keys
        self._fill_diemap()

        # create a "root" ProgramInfoStub object
        # only collect global variables with an actual location
        globalrefs = [ self.get_DIE_key(die) for die in get_global_var_DIEs(self.dwarfinfo) if var_DIE_has_location(die) ]
        # only collect functions that are not inlined
        functionrefs = [ self.get_DIE_key(die) for die in get_function_DIEs(self.dwarfinfo) if function_DIE_is_translatable(die) ]
        rootkey = self.make_stub(
            ProgramInfoStub(
                globalrefs=globalrefs,
                functionrefs=functionrefs
            )
        )
        self.db.set_root_key(rootkey)

        # map the DIEs to the Resolver stubs in the DB (recursively)
        for ref in (globalrefs + functionrefs):
            self.generate_DIE_stubs(ref)

        # make each variable/parameter point back to its parent function key
        # for functionref in functionrefs:
        #     functionstub = self.db.lookup(functionref).stub
        #     for varref in (functionstub.paramrefs + functionstub.varrefs):
        #         self.db.lookup(varref).stub.functionref = functionref

        # resolve the functions, variables, & types -> ProgramInfo
        proginfo = self.db.resolve_root()

        # for local variables with 'static' keyword, move these to globals
        for ref in self.static_local_refs:
            record = self.db.lookup(ref)
            if record and record.obj and record.obj.function:
                record.obj.function.vars.remove(record.obj)
                record.obj.function = None
                proginfo.globals.append(record.obj)
        
        return proginfo


def parse_from_dwarfinfo(dwarfinfo):
    parser = ParseDWARF(dwarfinfo)
    return parser.parse()

# produce a Translation object from the DWARF info
def parse_from_objfile(objfilepath):
    elffile, dwarfinfo = get_elf_dwarf_info(objfilepath)
    return parse_from_dwarfinfo(dwarfinfo)
    
def main():
    if len(sys.argv) < 2:
        print("Provide path to object / binary file to parse")
        exit(0)

    objfilepath = sys.argv[1]
    proginfo = parse_from_objfile(objfilepath)
    proginfo.print_summary()

if __name__ == "__main__":
    main()