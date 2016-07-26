## \package freud.parallel
#
# Methods to control parallel execution
#
import multiprocessing
import platform
import re
from . import _freud;

if (re.match("flux*", platform.node()) is not None) or (re.match("nyx*", platform.node()) is not None):
    _freud.setNumThreads(1);

class NumThreads:
    def __init__(self, N=None):
        self.restore_N = _freud._numThreads
        self.N = N

    def __enter__(self):
        _freud.setNumThreads(self.N)

    def __exit__(self, *args):
        _freud.setNumThreads(self.restore_N)
