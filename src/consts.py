from pathlib import Path
import os

### ----------- PATHS ----------
# the path to the parent directory of this module
SRC_DIR = Path(__file__).resolve().parent
# the path to the root directory of the repo
REPO_DIR = SRC_DIR.parent
# the path to the 'data' directory in the repository
DATA_DIR = REPO_DIR.joinpath("data")
# the location where Ghidra is installed
GHIDRA_BUILD_DIR = Path(os.environ["GHIDRA_BUILD"]).resolve()

### ---------- BENCHMARKS / PROGRAMS ----------
COREUTILS_PROG_NAMES = [
    '[', 'b2sum', 'base32', 'base64', 'basename', 'basenc', 'cat', 'chcon',
    'chgrp', 'chmod', 'chown', 'chroot', 'cksum', 'comm', 'cp', 'csplit',
    'cut', 'date', 'dd', 'df', 'dir', 'dircolors', 'dirname', 'du', 'echo', 'env',
    'expand', 'expr', 'factor', 'false', 'fmt', 'fold', 'groups', 'head', 'hostid',
    'id', 'join', 'kill', 'link', 'ln', 'logname', 'ls',
    'md5sum', 'mkdir', 'mkfifo', 'mknod', 'mktemp', 'mv', 'nice', 'nl', 'nohup',
    'nproc', 'numfmt', 'od', 'paste', 'pathchk', 'pinky', 'pr', 'printenv', 'printf',
    'ptx', 'pwd', 'readlink', 'realpath', 'rm', 'rmdir', 'runcon', 'seq', 'sha1sum',
    'sha224sum', 'sha256sum', 'sha384sum', 'sha512sum', 'shred', 'shuf', 'sleep', 'sort',
    'split', 'stat', 'stdbuf', 'stty', 'sum', 'sync', 'tac', 'tail', 'tee', 'test', 'timeout',
    'touch', 'tr', 'true', 'truncate', 'tsort', 'tty', 'uname', 'unexpand', 'uniq', 'unlink',
    'uptime', 'users', 'vdir', 'wc', 'who', 'whoami', 'yes'
]

# the path to the Coreutils benchmarks repository
COREUTILS_PATH = REPO_DIR.parent.joinpath("programs/coreutils-9.1")
# the path to the toy/test programs directory
TOY_PROGS_PATH = REPO_DIR.joinpath("programs/toy")

### ---------- CACHING / DEPENDENCY GROUPS -----------
PICKLE_CACHE_DIR = REPO_DIR.joinpath("cache")
LANG_DEPS = [ dep for dep in SRC_DIR.glob("lang*.py") ]
COMPARE_DEPS = [ dep for dep in SRC_DIR.glob("compare*.py") ]
RESOLVE_DEPS = [ dep for dep in SRC_DIR.glob("resolve*.py") ]

