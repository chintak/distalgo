# Copyright (c) 2010-2015 Bo Lin
# Copyright (c) 2010-2015 Yanhong Annie Liu
# Copyright (c) 2010-2015 Stony Brook University
# Copyright (c) 2010-2015 The Research Foundation of SUNY
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import sys
import logging
import argparse

__version__ = "1.0.0b16"

from .api import entrypoint
from .common import set_global_options

if hasattr(sys, '_real_argv'):
    sys.argv[0] = sys._real_argv

log = logging.getLogger(__name__)
formatter = logging.Formatter(
    '[%(asctime)s]%(name)s:%(levelname)s: %(message)s')
log._formatter = formatter

def parseArgs():
    LogLevelNames = [n.lower() for n in logging._nameToLevel]

    parser = argparse.ArgumentParser(fromfile_prefix_chars='@')
    # parser.add_argument("-s", "--perffile")
    # parser.add_argument("-u", "--dumpfile")
    parser.add_argument('--iterations', type=int, default=1,
                        help="number of times to run the program, defaults to 1.")
    parser.add_argument("--nolog", action="store_true", default=False,
                        help="disables all logging output.")
    parser.add_argument("-f", "--logfile", action="store_true", default=False,
                        help="creates a log file for this run.")
    parser.add_argument("--logfilename",
                        help="file name of the log file, defaults to appending"
                        "'.log' to the source file name.")
    parser.add_argument("--logdir")
    parser.add_argument("-L", "--logconsolelevel",
                        choices=LogLevelNames, default="info",
                        help="severity level of logging messages to print to "
                        "the console, defaults to 'info'.")
    parser.add_argument("-F", "--logfilelevel",
                        choices=LogLevelNames, default="debug",
                        help="severity level of logging messages to log to "
                        "the log file, defaults to 'debug'.")
    parser.add_argument("-i", "--load-inc-module",
                        action="store_true", default=False,
                        help="if set, try to load the incrementalized "
                        "interface module.")
    parser.add_argument("-C", "--control-module-name", default=None,
                        help="name of the control module. If set, "
                        "results from the inc-module will be compared "
                        "against results from this module. Any mismatch will "
                        "raise IntrumentationError. Defaults to no control "
                        "module.")
    parser.add_argument("-m", "--inc-module-name",
                        help="name of the incrementalized interface module, "
                        "defaults to source module name + '_inc'. ")
    parser.add_argument("-r", "--recompile", dest="recompile",
                        help="force recompile DistAlgo source file. ",
                        action="store_true", default=False)
    parser.add_argument("-c", "--compiler-flags", default="",
                        help="flags to pass to the compiler, if recompiling "
                        "is required.")

    parser.add_argument("--max-retries", type=int, default=5,
                        help="maximum number of times to try binding to a port "
                        "during protocol initialization. If a protocol fails "
                        "to bind a port after this many retries, the process "
                        "will terminate.")
    parser.add_argument("--min-port", type=int, default=10000,
                        help="lowest port number for TCP and UDP protocols. "
                        "Each process will choose a random port number "
                        "between `min-port' and `max-port'.")
    parser.add_argument("--max-port", type=int, default=65535,
                        help="highest port number for TCP and UDP protocols. "
                        "Ports for each process will be chosen randomly "
                        "between `min-port' and `max-port'.")

    parser.add_argument("--handling", # default="one",
                        choices=['one', 'all', 'snapshot'],
                        help="specify the handling semantics for yield points."
                        " Overrides configurations declared in the program.")
    parser.add_argument("--clock", # default="None",
                        choices=['lamport'],
                        help="specify the logical clock type."
                        " Overrides configurations declared in the program.")
    parser.add_argument("--channel", # default="",
                        choices=['fifo', 'reliable', 'nonfifo', 'unreliable'],
                        action="append",
                        help="specify the channel properties."
                        " Overrides configurations declared in the program.")

    parser.add_argument("-H", "--host", default='localhost',
                        help="host name of local node; defaults to 'localhost'.")
    parser.add_argument("--start-method", default=None, choices=['fork', 'spawn'],
                        help="choose the start method for spawning child processes."
                        " 'fork' is the default method on UNIX-like systems,"
                        " 'spawn' is the default method on Windows systems.")
    parser.add_argument("-v", "--version", action="version", version=__version__)
    parser.add_argument("file",
                        help="DistAlgo source file to run.")
    parser.add_argument("args", nargs=argparse.REMAINDER,
                        help="arguments passed to program in sys.argv[1:].")

    return parser.parse_args()

def libmain():
    """
    Main program entry point. Parses command line options, sets up global
    variables, and calls the 'main' function of the DistAlgo program.
    """

    cmdparams = parseArgs()
    set_global_options(cmdparams)
    entrypoint()

def die(mesg = None):
    if mesg != None:
        sys.stderr.write(mesg + "\n")
    sys.exit(1)

if __name__ == '__main__':
    libmain()
