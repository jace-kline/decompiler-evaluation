from elftools.elf.elffile import ELFFile
from elftools.common.py3compat import bytes2str
from elftools.dwarf.dwarf_expr import DW_OP_name2opcode
from elftools.dwarf.constants import *
from elftools.dwarf.locationlists import LocationParser
from elftools.dwarf.ranges import RangeEntry, BaseAddressEntry
from elftools.dwarf.dwarf_expr import DWARFExprParser, DWARFExprOp
from lang import *

## Utility functions

# This exception shall be raised if there is no ELF/DWARF info or no debugging info is present
class ELF_DWARF_Exception(Exception):
    pass

# Represents the "form" that a given attribute value can take.
# Used when determining how to interpret attribute value bytes.
# Pg. 213 in https://dwarfstd.org/doc/DWARF5.pdf
class DWARFClass(object):
    ADDRESS = 0
    ADDRPTR = 1
    BLOCK = 2
    CONSTANT = 3
    EXPRLOC = 4
    FLAG = 5
    LINEPTR = 6
    LOCLIST = 7
    LOCLISTSPTR = 8
    MACPTR = 9
    RNGLIST = 10
    RNGLISTSPTR = 11
    REFERENCE = 12
    STRING = 13
    STROFFSETSPTR = 14

class2forms = {
    DWARFClass.ADDRESS: ["DW_FORM_addr", "DW_FORM_addrx", "DW_FORM_addrx1", "DW_FORM_addrx2", "DW_FORM_addrx3", "DW_FORM_addrx4"],
    DWARFClass.ADDRPTR: ["DW_SEC_OFFSET"],
    DWARFClass.BLOCK: ["DW_FORM_block1", "DW_FORM_block2", "DW_FORM_block4", "DW_FORM_block"],
    DWARFClass.CONSTANT: ["DW_FORM_data1", "DW_FORM_data2", "DW_FORM_data4", "DW_FORM_data8", "DW_FORM_data16", "DW_FORM_sdata", "DW_FORM_udata", "DW_FORM_implicit_const"],
    DWARFClass.EXPRLOC: ["DW_FORM_exprloc"],
    DWARFClass.FLAG: ["DW_FORM_flag", "DW_FORM_flag_present"],
    DWARFClass.LINEPTR: ["DW_FORM_sec_offset"],
    DWARFClass.LOCLIST: ["DW_FORM_loclistx", "DW_FORM_sec_offset"],
    DWARFClass.LOCLISTSPTR: ["DW_FORM_sec_offset"],
    DWARFClass.MACPTR: ["DW_FORM_sec_offset"],
    DWARFClass.RNGLIST: ["DW_FORM_rnglistx","DW_FORM_sec_offset"],
    DWARFClass.RNGLISTSPTR: ["DW_FORM_sec_offset"],
    DWARFClass.REFERENCE: ["DW_FORM_ref1", "DW_FORM_ref2", "DW_FORM_ref4", "DW_FORM_ref8", "DW_FORM_ref_udata", "DW_FORM_ref_addr", "DW_FORM_ref_sig8", "DW_FORM_ref_sup4", "DW_FORM_ref_sup8"],
    DWARFClass.STRING: ["DW_FORM_string", "DW_FORM_strp", "DW_FORM_line_strp", "DW_FORM_strp_sup", "DW_FORM_strx", "DW_FORM_strx1", "DW_FORM_strx2", "DW_FORM_strx3", "DW_FORM_strx4"],
    DWARFClass.STROFFSETSPTR: ["DW_FORM_sec_offset"]
}

def form_in_class(form, _class):
    return form in class2forms[_class]

# parse the ELF and DWARF info from a given object file (specified by its path)
def get_elf_dwarf_info(objfilepath):
    # objfilepath = "./progs/varcases_debug_O0.bin" # "./progs/p0"

    # raises Exception if no file or can't be opened
    f = open(objfilepath, 'rb')
    elffile = ELFFile(f)

    if elffile is None:
        raise ELF_DWARF_Exception("Could not parse ELF info from input file")

    if not elffile.has_dwarf_info():
        raise ELF_DWARF_Exception("File has no DWARF info")

    dwarfinfo = elffile.get_dwarf_info()

    if not dwarfinfo.has_debug_info:
        raise ELF_DWARF_Exception("DWARF info has no debug info")

    return elffile, dwarfinfo

# get all DIE entries across all CUs
# ignore null DIEs
def get_all_DIEs(dwarfinfo):
    dies = []
    for cu in dwarfinfo.iter_CUs():
        for die in cu.iter_DIEs():
            if not die.is_null():
                dies.append(die)
    return dies

def get_DIE_by_cu_offset(dwarfinfo, cu_offset, offset):
    return dwarfinfo.get_DIE_from_refaddr(offset, cu=dwarfinfo.get_CU_at(cu_offset))

def get_DIE_attr_ref_DIE(die, attr):
    try:
        return die.get_DIE_from_attribute(attr)
    except:
        return None

def get_DIE_attr_ref_DIE_follow_abstract_origin(die, attr):
    try:
        return die.get_DIE_from_attribute(attr)
    except:
        abstractdie = get_DIE_attr_ref_DIE(die, "DW_AT_abstract_origin")
        if abstractdie is not None:
            return get_DIE_attr_ref_DIE(abstractdie, attr)
        else:
            return None

# follows links (DW_AT_abstract_origin, DW_AT_specification)
def get_DIE_attr_ref_DIE_follow(die, attr):
    FOLLOW_ATTRS = ("DW_AT_abstract_origin", "DW_AT_specification")
    try:
        return die.get_DIE_from_attribute(attr)
    except:
        for at in FOLLOW_ATTRS:
            followdie = get_DIE_attr_ref_DIE(die, at)
            if followdie is not None:
                return get_DIE_attr_ref_DIE_follow(followdie, attr)
        return None


# extract the low and high pc values for a function-like DIE
# DIE -> (int, int) | None
# returns None if either of the attributes are not present
def get_DIE_low_high_pc(die):
    lowpc = get_DIE_attr_value(die, "DW_AT_low_pc")
    highpc_attr = get_DIE_attr(die, "DW_AT_high_pc")

    if lowpc is None or highpc_attr is None:
        return None

    # TODO: should we be adding 1 to get to the address of the following instruction?
    highpc = None
    if form_in_class(highpc_attr.form, DWARFClass.ADDRESS):
        highpc = highpc_attr.value + 1
    elif form_in_class(highpc_attr.form, DWARFClass.CONSTANT):
        highpc = lowpc + highpc_attr.value + 1
    else:
        raise NotImplementedError(highpc_attr.form)

    # TODO: find out why this sometimes happens?? -> because we weren't adding 1 to highpc before
    if highpc < lowpc:
        highpc = lowpc
    
    return (lowpc, highpc)

# DIE -> [(int, int)] | None
def get_DIE_ranges(die):
    rnglist = get_DIE_rangelist(die)
    if rnglist is None:
        return None
    
    base = 0
    ranges = []
    for rng in rnglist:
        if type(rng) == RangeEntry:
            ranges.append((base + rng.begin_offset, base + rng.end_offset))
        elif type(rng) == BaseAddressEntry:
            base = rng.base_address
    return ranges

# Extract the ranges of PC addrs specified by the 'DW_AT_ranges' attribute
# for a given DIE.
def get_DIE_rangelist(die):
    rngattr = get_DIE_attr(die, "DW_AT_ranges")
    if rngattr is None:
        return None
    offset = rngattr.value # possible forms = ["DW_FORM_rnglistx", "DW_FORM_sec_offset"]
    return get_range_list_at_offset(die.dwarfinfo, offset, cu=die.cu)
    
def get_range_list_at_offset(dwarfinfo, offset, cu=None):
    rnglists = dwarfinfo.range_lists()
    if rnglists is None:
        return None
    return rnglists.get_range_list_at_offset(offset, cu=cu)

# Attempts to parse the low PC & high PC via the 'DW_AT_low_pc' and 'DW_AT_high_pc' attributes.
# If not successful, attempts to get a list of ranges from the 'DW_AT_ranges' attribute.
# Returns a list of ranges for the scope-like DIE or None (if no range info present).
# DIE -> [(int, int)] | None
def get_scope_DIE_pc_ranges(die):
    res = get_DIE_low_high_pc(die)
    if res is not None:
        return [res]
    
    return get_DIE_ranges(die)

def is_variadic_function_DIE(die):
    for childdie in die.iter_children():
        if childdie.tag == "DW_TAG_unspecified_parameters":
            return True
    return False

def is_scopelike_DIE(die):
    return die.tag in [
        "DW_TAG_subprogram",
        "DW_TAG_lexical_scope",
        "DW_TAG_inlined_subroutine"
    ]

def is_functionlike_DIE(die):
    return die.tag == "DW_TAG_subprogram"

def is_variablelike_DIE(die):
    return die.tag in [
        "DW_TAG_variable",
        "DW_TAG_formal_parameter"
    ]

def is_artificial_DIE(die):
    res = get_DIE_attr_value(die, "DW_AT_artificial")
    return res is not None and bool(res)

def get_function_DIEs(dwarfinfo):
    dies = get_all_DIEs(dwarfinfo)
    return [ die for die in dies if is_functionlike_DIE(die) ]

def get_function_DIE_by_name(dwarfinfo, fname):
    fndies = [ die for die in get_function_DIEs(dwarfinfo) if get_DIE_name(die) == fname ]
    return fndies[0] if len(fndies) > 0 else None

def get_DIE_parent_function_DIE(die):
    parent = die.get_parent()
    while parent is not None:
        if is_functionlike_DIE(parent):
            return parent
        parent = parent.get_parent()

# Are this function's instance(s) inlined by the compiler?
# DIE -> bool
def function_DIE_is_inlined(die):
    inline_attr = get_DIE_attr_follow_abstract_origin(die, "DW_AT_inline")
    return False if inline_attr is None else (inline_attr.value in [DW_INL_inlined, DW_INL_declared_inlined])

def function_DIE_has_location(die):
    return get_DIE_attr(die, "DW_AT_low_pc") is not None

# A function is only translatable if it is not inlined
# AND it has instructions in the binary.
def function_DIE_is_translatable(die):
    return not function_DIE_is_inlined(die) and function_DIE_has_location(die)

# Does the given variable-like DIE have any location information?
# If not, then assume it is optimized away
def var_DIE_has_location(die):
    return len(get_DIE_liveranges(die)) > 0

# for a given variable/parameter DIE, get the PC ranges of the most immediate parent DIE that
# is considered a "scope". Must have 'DW_AT_low_pc', 'DW_AT_high_pc' OR 'DW_AT_ranges'.
# DIE -> [(int, int)] | None
def get_DIE_parent_scope_pc_ranges(die):
    parent = die.get_parent()
    while parent is not None:
        if is_scopelike_DIE(parent):
            ranges = get_scope_DIE_pc_ranges(parent)
            if ranges is not None:
                return ranges
        parent = parent.get_parent()

# if fname = None, assume global variable
def get_var_DIE_by_name(dwarfinfo, varname, fname=None):
    targetdies = []
    if fname is None:
        targetdies = get_global_var_DIEs(dwarfinfo)
    else:
        fndie = get_function_DIE_by_name(dwarfinfo, fname)
        if fndie is None:
            return None
        else:
            paramdies, vardies = get_param_var_DIEs(fndie)
            targetdies = paramdies + vardies
    targets = [ die for die in targetdies if get_DIE_name(die) == varname ]
    return targets[0] if len(targets) > 0 else None

# get global variables
# any 'DW_TAG_variable' DIEs that are direct descendants of the root
# are assumed to be global variables
def get_global_var_DIEs(dwarfinfo):
    globals = []
    for cu in dwarfinfo.iter_CUs():
        rootdie = cu.get_top_DIE()
        globals += [ die for die in rootdie.iter_children() if die.tag == "DW_TAG_variable" ]
    return globals

# given a DIE and an attribute name, fetch the attr value (or None if doesn't exist)
def get_DIE_attr_value(die, attr):
    res = die.attributes.get(attr, None)
    return None if res is None else res.value

# given a DIE and an attribute name, fetch the attribute (AttributeValue object or None if doesn't exist)
def get_DIE_attr(die, attr):
    res = die.attributes.get(attr, None)
    return None if res is None else res

def get_DIE_attr_follow_abstract_origin(die, attr):
    res = get_DIE_attr(die, attr)
    if res is not None:
        return res
    else:
        origindie = get_DIE_attr_ref_DIE(die, "DW_AT_abstract_origin")
        return get_DIE_attr(origindie, attr) if origindie is not None else None

def get_DIE_name_follow_abstract_origin(die):
    res = get_DIE_attr_follow_abstract_origin(die, "DW_AT_name")
    return bytes2str(res.value) if res is not None else None

def DIE_has_attr(die, attr):
    return get_DIE_attr(die, attr) is not None

# return the "DW_AT_name" attribute of the DIE as a string
def get_DIE_name(die):
    attr = die.attributes.get("DW_AT_name", None)
    return bytes2str(attr.value) if attr is not None else None

# get the children variable-like DIEs of a given function (or lexical scope) DIE
# called recursively on sub-scopes
# returns (parameter DIEs, variable DIEs)
# varsonly: indicates that this was called from top level of resolving function params & vars
# if not top level (varsonly=True), do not include formal parameters (probably from inlined function)
def get_param_var_DIEs(scopedie, varsonly=False):

    if not scopedie.has_children:
        return ([], [])
    
    paramdies = []
    vardies = []
    for die in scopedie.iter_children():
        if not varsonly and die.tag == "DW_TAG_formal_parameter":
            paramdies.append(die)

        elif die.tag == "DW_TAG_variable":
            vardies.append(die)

        elif die.tag in ["DW_TAG_lexical_block", "DW_TAG_inlined_subroutine"]: # recurse
            _, vdies = get_param_var_DIEs(die, varsonly=True)
            vardies += vdies

    return (paramdies, vardies)

# Location helper functions

def get_location_lists(dwarfinfo): # LocationLists
    return dwarfinfo.location_lists()

def get_location_list_at_offset(dwarfinfo, offset): # [LocationEntry]
    return dwarfinfo.location_lists().get_location_list_at_offset(offset)

# given a variable-like DIE,
# produce either a LocationExpr object (single location)
# OR a list of LocationEntry, BaseAddressEntry, and LocationViewPair objects (multiple locations)
def get_DIE_locs(die):
    # instantiate a LocationParser object
    loclists = get_location_lists(die.dwarfinfo)
    dwarfversion = die.cu["version"]
    locparser = LocationParser(loclists)

    locattr = get_DIE_attr(die, "DW_AT_location")
    if locattr is None or not locparser.attribute_has_location(locattr, dwarfversion):
        return None
    else:
        return locparser.parse_from_attribute(locattr, dwarfversion, die=die)

# [(int, int)] -> (int, int)
def merge_ranges(ranges):
    if len(ranges) == 0:
        raise Exception("ranges list must be non-empty")
    low, high = ranges[0]
    for l, h in ranges[1:]:
        if l < low:
            low = l
        if h > high:
            high = h
    return (low, high)

# given a variable-like DIE and the start and end Address objects for its
# parent lexical scope (function / lexical scope / inlined function block),
# produce a list of AddressLiveRange objects
# DIE -> [AddressLiveRange]
def get_DIE_liveranges(die, scopestartpc=None, scopeendpc=None):
    locs = get_DIE_locs(die)
    if locs is None:
        return []
    elif type(locs) == list:
        liveranges = []
        for loc in locs:
            try:
                # type(loc) == LocationEntry
                addr = parse_dwarf_locexpr_addr(die.dwarfinfo, loc.loc_expr)
                if addr is not None:
                    startpc = AbsoluteAddress(loc.begin_offset)
                    endpc = AbsoluteAddress(loc.end_offset)
                    liveranges.append(AddressLiveRange(
                        addr=addr,
                        startpc=startpc,
                        endpc=endpc
                    ))
            except AttributeError:
                # type(loc) == BaseAddressEntry | LocationViewPair
                pass
        return liveranges
    else: # type(locs) == LocationExpr
        addr = parse_dwarf_locexpr_addr(die.dwarfinfo, locs.loc_expr)
        return [AddressLiveRange(
            addr=addr,
            startpc=scopestartpc,
            endpc=scopeendpc
        )] if addr is not None else []

# [int] -> Address | None
def parse_dwarf_locexpr_addr(dwarfinfo, locexpr):
    expr_ops = parse_dwarf_expr(dwarfinfo, locexpr) # [DWARFExprOp]
    return parse_dwarf_expr_ops_to_addr(expr_ops) # Address | None

# [int] -> [DWARFExprOp]
def parse_dwarf_expr(dwarfinfo, expr):
    exprparser = DWARFExprParser(dwarfinfo.structs)
    return exprparser.parse_expr(expr)

# [DWARFExprOp] -> Address | None (if not a location)
def parse_dwarf_expr_ops_to_addr(expr_ops):

    # if the expression is only a single operation...
    if len(expr_ops) == 1:
        expr_op = expr_ops[0]
        # absolute address?
        if expr_op.op_name == "DW_OP_addr":
            addr = expr_op.args[0]
            return AbsoluteAddress(addr)

        # base register offset address?
        elif expr_op.op_name == "DW_OP_fbreg":
            offset = expr_op.args[0]
            # TODO: Avoid implicit assumption of x86-64 & RBP here
            return StackAddress(offset)

        # stored in register?
        elif DW_OP_name2opcode["DW_OP_reg0"] <= expr_op.op <= DW_OP_name2opcode["DW_OP_reg31"]:
            regnum = expr_op.op - DW_OP_name2opcode["DW_OP_reg0"]
            return RegisterAddress(regnum)

        elif expr_op.op_name == "DW_OP_regx":
            regnum = expr_op.args[0]
            return RegisterAddress(regnum)

        # offset from a register?
        elif DW_OP_name2opcode["DW_OP_breg0"] <= expr_op.op <= DW_OP_name2opcode["DW_OP_breg31"]:
            regnum = expr_op.op - DW_OP_name2opcode["DW_OP_reg0"]
            offset = expr_op.args[0]
            return RegisterOffsetAddress(regnum, offset)

        elif expr_op.op_name == "DW_OP_bregx":
            regnum = expr_op.args[0]
            offset = expr_op.args[1]
            return RegisterOffsetAddress(regnum, offset)

        else:
            raise NotImplementedError(expr_ops)
        
    elif len(expr_ops) > 1:
        # if the last operation is 'DW_OP_stack_value', we know that there is no
        # memory/register location allocated -> return None
        if expr_ops[-1].op_name == "DW_OP_stack_value":
            return None

        else:
            raise NotImplementedError(expr_ops)

    return None
        

# # given a DIE with a 'DW_AT_location' OR 'DW_AT_low_pc' attribute,
# # returns an Address object
# # if attribute non-existent, return None
# def parse_dwarf_addr(locexpr):

#     op = locexpr[0] # the operation specifier
#     bs = locexpr[1:] # the bytes representing location/offset

#     # absolute address
#     if op == DW_OP_name2opcode["DW_OP_addr"]:
#         addr = le_unsigned_decode(bs)
#         return Address(
#             addrspace=AddressSpace.GLOBAL,
#             offset=addr
#         )

#     # offset from stack frame register's base pointer (DW_AT_frame_base)
#     elif op == DW_OP_name2opcode["DW_OP_fbreg"]:
#         offset = sleb128_decode(bs)
#         return Address(
#             addrspace=AddressSpace.STACK,
#             offset=offset
#         )

#     # other
#     else:
#         raise NotImplementedError(op)

# # bs = sequence of integer bytes in little endian order
# # reverse the order and concatenate
# def le_unsigned_decode(bs):
#     val = 0
#     for i, b in enumerate(bs):
#         val |= (b << (8 * i))
    
#     return val

# # bs = sequence of integer bytes
# # little-endian 128 bit variable encoding
# def sleb128_decode(bs):
#     # strip the leftmost (8th) bit in each byte
#     _bs = [ b & 0x7f for b in bs ]

#     # loop over each 7-bit chunk
#     # for each chunk, shift its 7 bits left by the byte index * 7
#     # concatenate the shifted chunks together with OR operator
#     # this also reverses the bytes to big endian
#     val = 0
#     for i, b in enumerate(_bs):
#         val |= (b << (7 * i))

#     # sign-extend to fill full bytes
#     nbits = 7 * len(_bs) # number of bits in val
#     sign = val >> (nbits - 1) # leftmost bit = sign bit
#     fillbits = 8 - (nbits % 8) # number of bits to fill to reach full bytes
#     nbytes = (nbits + fillbits) // 8 # number of total bytes of the output

#     # build the fill bit sequence
#     fill = 0
#     for i, b in enumerate([ sign for _ in range(0, fillbits) ]):
#         fill |= (b << i)

#     # prepend the fill bits to the original val
#     val |= (fill << nbits)

#     # force Python to represent this as a (possibly) signed integer (2's complement)
#     val = int.from_bytes(val.to_bytes(nbytes, 'big'), 'big', signed=(sign == 1))

#     return val
