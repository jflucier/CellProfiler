"""Plugin modules - redirect module loads to the user's plugin
directory.

CellProfiler is distributed under the GNU General Public License.
See the accompanying file LICENSE for details.

Copyright (c) 2003-2009 Massachusetts Institute of Technology
Copyright (c) 2009-2013 Broad Institute
All rights reserved.

Please see the AUTHORS file for credits.

Website: http://www.cellprofiler.org
"""
__version__ = "$Revision: 9144 $"


# These examples:
# http://blog.dowski.com/2008/07/31/customizing-the-python-import-system/
# http://www.secomputing.co.uk/2009/05/importing-python-packages-in-memory.html
# were helpful when writing this code.

import imp
import sys
import os.path
import glob
import cellprofiler.preferences as cpprefs


def plugin_list():
    plugin_dir = cpprefs.get_plugin_directory()
    if plugin_dir is not None and os.path.isdir(plugin_dir):
        file_list = glob.glob(os.path.join(plugin_dir, '*.py'))
        return [os.path.basename(f)[:-3] for f in file_list
                if not f.endswith('__init__.py')]
    return []


class PluginImporter(object):
    def find_module(self, fullname, path=None):
        if not fullname.startswith('cellprofiler.modules.plugins'):
            return None
        prefix, modname = fullname.rsplit('.', 1)
        if prefix != 'cellprofiler.modules.plugins':
            return None
        if os.path.exists(os.path.join(cpprefs.get_plugin_directory(), modname + '.py')):
            return self
        return None
 
    def load_module(self, fullname):
        if fullname in sys.modules:
            return sys.modules[fullname]

        prefix, modname = fullname.rsplit('.', 1)
        assert prefix == 'cellprofiler.modules.plugins'

        try:
            mod = imp.new_module(fullname)
            sys.modules[fullname] = mod
            mod.__loader__ = self
            mod.__file__ = os.path.join(cpprefs.get_plugin_directory(), modname + '.py')

            contents = open(mod.__file__, "r").read()
            exec compile(contents, mod.__file__, "exec") in mod.__dict__
            return mod
        except:
            if fullname in sys.module:
                del sys.modules[fullname]

sys.meta_path.append(PluginImporter())
