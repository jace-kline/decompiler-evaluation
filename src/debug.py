from parse_dwarf import *
from build_parse import *
from metrics import *

# prognames = [ "ndarray", "typecases", "p0", "structcases" ]
# progs = [ ToyProgram(progname) for progname in prognames ]
# metrics_groups = make_metrics()

def find_erroneous_overlaps(proginfo: ProgramInfo) -> List[Tuple[Varnode, Varnode]]:
    unopt_proginfo = UnoptimizedProgramInfo(proginfo)
    gbls = unopt_proginfo.get_unoptimized_globals()
    fns = unopt_proginfo.get_unoptimized_functions().values()
    return sum([ ConstPCVariableSetSnapshot(fn.get_varnodes())._find_overlaps() for fn in fns ], []) \
        + ConstPCVariableSetSnapshot(gbls)._find_overlaps()

def _name(varnode: Varnode) -> str:
    return varnode.get_var().get_name()

def _f(proginfo: ProgramInfo) -> Tuple[str, str]:
    return [ (_name(l), _name(r)) for (l, r) in find_erroneous_overlaps(proginfo) ]

# s = ""
# for prog in COREUTILS_PROGS:
#     # prog.build_if_not_valid(opts)
#     # prog.build_if_not_valid(dwarf_opts)
#     dwarf = ghidra = None
#     cmp = None
#     results = None
#     try:
#         dwarf, ghidra = parse_proginfo_pair(prog, opts)
#         # print(prog.get_name())
#         # print(_f(dwarf))
#         # print(_f(ghidra))
#         # print(),
#         cmp = UnoptimizedProgramInfoCompare2(
#             UnoptimizedProgramInfo(dwarf),
#             UnoptimizedProgramInfo(ghidra)
#         )
#         for metrics_group in metrics_groups:
#             compute_program_metrics(prog, opts, metrics_group)
#     except:
#         s += "\"{}\", ".format(prog.get_name())

# print(s)

# prog = ToyProgram("p1")

# dwarf_unopt, ghidra_unopt = cmp.get_left(), cmp.get_right()
# cmp_flip = cmp.flip()

def missed_varnodes_summary(cmp: UnoptimizedProgramInfoCompare2):
    compared_fn_records = cmp.select_function_compare_records(function_cmp_record_cond=function_compare_record_compared_filter)
    fn_cmps = [ fn_record.get_comparison() for fn_record in compared_fn_records ]
    fn_names = [ fn_record.get_unoptimized_function().get_function().get_name() for fn_record in compared_fn_records ]
    fn_scope_cmps = [ fn_cmp.get_variable_set_comparison() for fn_cmp in fn_cmps ] 
    gbl_scope_cmp = cmp.get_globals_comparison()
    named_scope_cmps: List[Tuple[str, ConstPCVariableSetSnapshotCompare2]] = [("GLOBALS", gbl_scope_cmp)] + list(zip(fn_names, fn_scope_cmps))
    for scopename, scopecmp in named_scope_cmps:
        varnode_records = scopecmp.select_varnode_compare_records(varnode_cmp_record_cond=varnode_base_filter)
        missed_records = [ record for record in varnode_records if record.get_compare_level() == VarnodeCompareLevel.NO_MATCH ]
        if missed_records:
            print(scopename)
        for varnode_record in missed_records:
            varnode = varnode_record.get_varnode()
            varname = varnode.get_var().get_name() if varnode.get_var() is not None else None
            addr_range = varnode.get_addr_range()
            print("\t{} @ ({}, {})".format(
                varname,
                # VarnodeCompareLevel.to_string(varnode_record.get_compare_level()),
                addr_range.get_start(),
                addr_range.get_end()
            ))
            
            right_varnodes = [ varnode for varnode in scopecmp.get_right().get_varnodes() if varnode_base_filter(varnode) ]
            overlapped_varnodes = [ varnode for varnode in right_varnodes if addr_range.does_overlap(varnode.get_addr_range()) ]
            for overlap_varnode in overlapped_varnodes:
                overlap_varname = overlap_varnode.get_var().get_name() if varnode.get_var() is not None else None
                overlap_addr_range = varnode.get_addr_range()
                print("\t{} @ ({}, {})".format(
                    overlap_varname,
                    # VarnodeCompareLevel.to_string(varnode_record.get_compare_level()),
                    overlap_addr_range.get_start(),
                    overlap_addr_range.get_end()
                ))

def test_progs_parse_compare(progs: List[Program]):
    dwarf_parser = get_parser("dwarf")
    ghidra_parser = get_parser("ghidra")

    opts = BuildOptions()
    dwarf_opts = BuildOptions(debug=True, strip=False, optimization=opts.optimization)

    errs = []
    for prog in progs:
        dwarf = ghidra = cmp = None
        try:
            dwarf = dwarf_parser(prog.get_binary_path(dwarf_opts))
        except:
            errs.append((prog.get_name(), "dwarf parse"))
            dwarf = None

        try:
            ghidra = ghidra_parser(prog.get_binary_path(opts))
        except:
            errs.append((prog.get_name(), "ghidra parse"))
            ghidra = None

        if dwarf is not None and ghidra is not None:
            try:
                cmp = compare2(dwarf, ghidra)
            except:
                errs.append((prog.get_name(), "comparison"))

        progname = prog.get_name()
        save_pickle(dwarf, PICKLE_CACHE_DIR.joinpath("{}_dwarf.pickle".format(progname)))
        save_pickle(ghidra, PICKLE_CACHE_DIR.joinpath("{}_ghidra.pickle".format(progname)))
        save_pickle(cmp, PICKLE_CACHE_DIR.joinpath("{}_cmp.pickle".format(progname)))

    for progname, reason in errs:
        print("{} : {}".format(progname, reason))

    return errs

# prog = CoreutilsProgram("ls")
# opts = BuildOptions(debug=False, strip=False, optimization=0)
# strip_opts = BuildOptions(debug=False, strip=True, optimization=0)
# dwarf_opts = BuildOptions(debug=True, strip=False, optimization=0)

# # failed = [ "chcon", "chgrp", "chmod", "cp", "du", "fmt", "mv", "rm", "sort" ]
# dwarf_parser = get_parser("dwarf")
# ghidra_parser = get_parser("ghidra")
# # opts = BuildOptions()
# # dwarf_opts = BuildOptions(debug=True, strip=False, optimization=opts.optimization)

# progname = "sort"
# prog = CoreutilsProgram(progname)
# dwarf = dwarf_parser(prog.get_binary_path(dwarf_opts))
# ghidra = ghidra_parser(prog.get_binary_path(strip_opts))
# cmp = compare2_uncached(dwarf, ghidra)

# metrics_groups = make_metrics()
# print(metrics_groups[7].get_name())

# errs = test_progs_parse_compare(COREUTILS_PROGS)

# print("------------------- DWARF vs GHIDRA -------------------")
# missed_varnodes_summary(cmp)
# print(cmp.show_summary())

# print(),
# print("------------------- DWARF -------------------")
# dwarf.print_summary()

# print(),
# print("------------------- GHIDRA vs DWARF -------------------")
# missed_varnodes_summary(cmp_flip)

# dwarf.print_summary()

def varnode_compare_records_missed(cmp: UnoptimizedProgramInfoCompare2, primitive: bool = False) -> List[VarnodeCompareRecord]:
    return varnode_compare_records_match_levels(cmp, [VarnodeCompareLevel.NO_MATCH], primitive=primitive)

def mangle_proginfo_save_name(parsername: str, prog: Program, opts: BuildOptions) -> str:
    return "{}.{}.pickle".format(prog.get_binary_name(opts), parsername)

def get_proginfo_save_path(parsername: str, prog: Program, opts: BuildOptions) -> Path:
    return PICKLE_CACHE_DIR.joinpath(mangle_proginfo_save_name(parsername, prog, opts))

def save_proginfo(proginfo: ProgramInfo, parsername: str, prog: Program, opts: BuildOptions):
    save_pickle(proginfo, get_proginfo_save_path(parsername, prog, opts))

def load_proginfo(parsername: str, prog: Program, opts: BuildOptions) -> ProgramInfo:
    return load_pickle(get_proginfo_save_path(parsername, prog, opts))

debug_opts = BuildOptions(debug=True, strip=False, optimization=0)
strip_opts = BuildOptions(debug=False, strip=True, optimization=0)

dwarf_parser = get_parser("dwarf")
# coreutils_progs = [ CoreutilsProgram(progname) for progname in COREUTILS_PROG_NAMES ]
# # ghidra_parser = get_parser("ghidra")
# fix_progs = []
# for prog in coreutils_progs:
#     try:
#         dwarf = dwarf_parser(prog.get_binary_path(debug_opts))
#     except:
#         fix_progs.append(prog)
# ghidra_debug = load_proginfo("ghidra", prog, debug_opts) # ghidra_parser(prog.get_binary_path(debug_opts))
# ghidra_strip = ghidra_parser(prog.get_binary_path(strip_opts))

# cmp_debug = compare2_uncached(dwarf, ghidra_debug)
# cmp_strip = compare2_uncached(dwarf, ghidra_strip)

# records_missed = varnode_compare_records_missed(cmp_debug)

fix_prognames = ['cksum', 'csplit', 'df', 'dir', 'du', 'expr', 'ln', 'ls', 'nl', 'ptx', 'readlink', 'realpath', 'tac', 'vdir', 'wc']
fix_progs = [ CoreutilsProgram(progname) for progname in fix_prognames ]

for prog in fix_progs:
    proginfo = dwarf_parser(prog.get_binary_path(debug_opts))
    save_proginfo(proginfo, "dwarf", prog, debug_opts)
    print(prog.get_name())
