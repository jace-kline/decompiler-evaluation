# Parse decompiled binary info from Ghidra to ProgramInfo object.
# Then either output the program info summary or the serialized object.
# @category: Research

import parse_ghidra
from parse_actions import do_action

def usage():
    print("ACTION: pickle <OUTPATH> | summary")

def parse_ghidra_exec(args):
    print(args)
    if not args:
        usage()
        exit(1)

    proginfo = parse_ghidra.parse()
    
    do_action(proginfo, args)


if __name__ == "__main__":
    args = list(getScriptArgs())
    parse_ghidra_exec(args)