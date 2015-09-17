#!/usr/bin/env python

from os.path import dirname, basename, isfile
from glob import glob
import importlib

module_files = glob(dirname(__file__) + '/*.py')
module_files = [f for f in module_files
                if isfile(f) and basename(f)[0] != '_']

module_names = [ basename(f)[:-3] for f in module_files ]
modules = [importlib.import_module('callbacks.'+m) for m in module_names]
callbacks = [m.callback for m in modules]
