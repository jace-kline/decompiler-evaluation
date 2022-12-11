import sys
import parse_dwarf
from parse_actions import do_action

def usage(scriptname):
    print("""
USAGE: python {} <BINARY> <ACTION>
<ACTION> ::= pickle <OUTPATH> | summary
""".format(scriptname))

def parse_dwarf_exec(args):

    numargs = len(args)
    if numargs < 3:
        usage(args[0])

    binpath = args[1]
    action = args[2:]

    proginfo = parse_dwarf.parse_from_objfile(binpath)

    do_action(proginfo, action)


if __name__ == "__main__":
    parse_dwarf_exec(sys.argv)