# Debug script for testing Ghidra API, etc.
# @category: Research

from ghidra.program.model.listing import VariableStorage
from ghidra.program.model.symbol import SymbolType
from parse_ghidra import *
from parse_ghidra_util import VariableInfo

parser = ParseGhidra()
util = parser.util

# Is the address a stack, global, or register?
# Address -> bool
def is_valid_address(addr):
    return addr.isConstantAddress() or addr.isMemoryAddress() or addr.isStackAddress() or addr.isRegisterAddress()

# get the referenced (from functions) global var highsymbols & print

# get the global var listings & print
# global_namespace = parser.curr.getGlobalNamespace()
# highsyms = util.get_referenced_global_var_highsyms()

# # Symbol -> bool
# def is_global_var_symbol(sym):
#     return sym.getSymbolType() in [SymbolType.LABEL, SymbolType.GLOBAL, SymbolType.GLOBAL_VAR]

# # Symbol -> GlobalVariableSymbolDB
# def extract_global_var_symbol_data(sym):
#     listing = parser.curr.getListing()
#     if is_global_var_symbol(sym):
#         return listing.getDefinedDataAt(sym.getAddress())

# syms = parser.curr.getSymbolTable().getAllSymbols(True)
# for sym in syms:
#     data = extract_global_var_symbol_data(sym)
#     if data:
#         dtype = data.getBaseDataType()
#         size = dtype.getLength()
#         if size > 0:
#             storage = VariableStorage(parser.curr, sym.getAddress(), size)
#             varinfo = VariableInfo(
#                 sym.getName(),
#                 dtype,
#                 storage
#             )
#             print(varinfo.get_storage_addresses())
#             # print("{} @ {}".format(sym, storage))

# gbls1 = util.get_referenced_global_vars()
# # for varinfo in gbls1:
# #     print(varinfo)

# gbls2 = util.get_global_vars()
# for varinfo in gbls2:
#     print("{} ... hash={}".format(varinfo, hash(varinfo)))

# gbls1_addrs = sum([gbl.get_storage_addresses() for gbl in gbls1], [])
# gbls2_addrs = sum([gbl.get_storage_addresses() for gbl in gbls2], [])

# for gbl1 in gbls1:
#     gbl1_addrs = gbl1.get_storage_addresses()
#     addrs_in = all([ addr in gbls2_addrs for addr in gbl1_addrs ])
#     print("{} : {}".format(
#         gbl1.getName(),
#         addrs_in
#     ))

# for gbl2 in gbls2:
#     gbl2_addrs = gbl2.get_storage_addresses()
#     addrs_in = all([ addr in gbls1_addrs for addr in gbl2_addrs ])
#     print("{} : {}".format(
#         gbl2.getName(),
#         addrs_in
#     ))
    

# for res in util.get_global_vars_symbol_data():
#     print(res)

# for highsym in highsyms:
#     print(highsym.getName())

# symbol_manager = None
# global_symbols = symbol_manager.getSymbols(global_namespace)
proginfo = parser.parse()
proginfo.print_summary()

# highfns = list(util.get_decompiled_functions())
# fns = [ highfn.getFunction() for highfn in highfns ]
# for highfn in highfns:
#     fn = highfn.getFunction()
#     highvars = get_highfn_local_var_highsyms(highfn)
#     lowvars = fn.getAllVariables()
#     print(fn)

#     print("\thigh-level variables:")
#     addrs = []
#     for highvar in highvars:
#         storage = highvar.getStorage()
#         varnodes = storage.getVarnodes()
#         varnode_addrs = [ varnode.getAddress() for varnode in varnodes ]
#         addrs += varnode_addrs
#         print("\t\t{} @ {}".format(highvar.getName(), varnode_addrs))
        

#     print("\tlow-level variables:")
#     for lowvar in lowvars:
#         storage = lowvar.getVariableStorage()
#         varnodes = storage.getVarnodes()
#         varnode_addrs = [ varnode.getAddress() for varnode in varnodes ]
#         does_overlap = any([ (varnode_addr in addrs) for varnode_addr in varnode_addrs ])
#         print("\t\t{} @ {} -> {}".format(lowvar, varnode_addrs, does_overlap))

# for highfn in highfns:
#     fn = highfn.getFunction()
#     paramvars = util.get_highfn_params(highfn)
#     localvars = util.get_highfn_local_vars(highfn)
# #     highsyms = get_highfn_local_var_highsyms(highfn)
# #     lowvars = fn.getAllVariables()

#     print(fn.getName())
#     # print(paramvars)
#     # print(localvars)
    
# #     print(merge_low_high_vars(lowvars, highsyms))
# #     print
#     print("\tparams:")
#     for param in paramvars:
#         print("\t\t{}".format(param))

#     print("\tlocals:")
#     for local in localvars:
#         print("\t\t{}".format(local))

# gblhighsyms = list(util.get_referenced_global_vars())
# localhighsyms = sum([ list(util.get_highfn_local_vars(highfn)) for highfn in util.get_decompiled_functions()], [])
# highsyms = gblhighsyms + localhighsyms

# addrs = []
# for highsym in highsyms:
#     storage = highsym.getStorage()
#     varnodes = storage.getVarnodes()
#     varnode_addrs = [ varnode.getAddress() for varnode in varnodes ]
#     addrs += varnode_addrs

# for addr in addrs:
#     space = addr.getAddressSpace()
#     spacename = space.getName()
#     print("{} in {}".format(
#         addr,
#         space
#     ))
