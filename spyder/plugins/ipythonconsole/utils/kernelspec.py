# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
# (see spyder/__init__.py for details)

"""
Kernel spec for Spyder kernels
"""

# Standard library imports
import logging
import os
import os.path as osp
import sys

# Third party imports
from jupyter_client.kernelspec import KernelSpec
# Local imports
from spyder.config.base import SAFE_MODE, running_under_pytest
from spyder.config.manager import CONF
from spyder.py3compat import PY2, iteritems, to_binary_string, to_text_string
from spyder.utils.conda import (add_quotes, get_conda_activation_script,
                                get_conda_env_path, is_conda)
from spyder.utils.encoding import to_unicode_from_fs
from spyder.utils.environ import clean_env
from spyder.utils.misc import add_pathlist_to_PYTHONPATH, get_python_executable
from spyder.utils.programs import is_python_interpreter

# Constants
HERE = os.path.abspath(os.path.dirname(__file__))
logger = logging.getLogger(__name__)


def get_activation_script(quote=False):
    """
    Return path for bash/batch conda activation script to run spyder-kernels.

    If `quote` is True, then quotes are added if spaces are found in the path.
    """
    scripts_folder_path = os.path.join(os.path.dirname(HERE), 'scripts')
    if os.name == 'nt':
        script = 'spyder-kernels.bat'
    else:
        script = 'spyder-kernels.sh'

    script_path = os.path.join(scripts_folder_path, script)

    if quote:
        script_path = add_quotes(script_path)

    return script_path


class SpyderKernelSpec(KernelSpec):
    """Kernel spec for Spyder kernels"""

    def __init__(self, is_cython=False, is_pylab=False,
                 is_sympy=False, **kwargs):
        super(SpyderKernelSpec, self).__init__(**kwargs)
        self.is_cython = is_cython
        self.is_pylab = is_pylab
        self.is_sympy = is_sympy

        self.display_name = 'Python 2 (Spyder)' if PY2 else 'Python 3 (Spyder)'
        self.language = 'python2' if PY2 else 'python3'
        self.resource_dir = ''

    @property
    def argv(self):
        """Command to start kernels"""
        # Python interpreter used to start kernels
        if CONF.get('main_interpreter', 'default'):
            pyexec = get_python_executable()
        else:
            # Avoid IPython adding the virtualenv on which Spyder is running
            # to the kernel sys.path
            os.environ.pop('VIRTUAL_ENV', None)
            pyexec = CONF.get('main_interpreter', 'executable')
            if not is_python_interpreter(pyexec):
                pyexec = get_python_executable()
                CONF.set('main_interpreter', 'executable', '')
                CONF.set('main_interpreter', 'default', True)
                CONF.set('main_interpreter', 'custom', False)

        is_different_interpreter = pyexec != sys.executable

        # Fixes spyder-ide/spyder#3427.
        if os.name == 'nt':
            dir_pyexec = osp.dirname(pyexec)
            pyexec_w = osp.join(dir_pyexec, 'pythonw.exe')
            if osp.isfile(pyexec_w):
                pyexec = pyexec_w

        # Command used to start kernels
        if is_different_interpreter and is_conda():
            # If this is a conda environment we need to call an intermediate
            # activation script to correctly activate the spyder-kernel

            # If changes are needed on this section make sure you also update
            # the activation scripts at spyder.plugins.ipythonconsole.scripts
            if os.name == 'nt':
                import ctypes
                codepage = str(ctypes.cdll.kernel32.GetACP())
                kernel_cmd = [
                    get_activation_script(quote=True),
                    'chcp {codepage}'.format(codepage=codepage),
                    get_conda_activation_script(quote=True),
                    get_conda_env_path(pyexec, quote=True),
                    pyexec,
                    '-f',
                    '{connection_file}'
                ]
            else:
                kernel_cmd = [
                    get_activation_script(quote=True),
                    get_conda_activation_script(quote=True),
                    get_conda_env_path(pyexec, quote=True),
                    pyexec,
                    '-f',
                    '{connection_file}'
                ]
        else:
            kernel_cmd = [
                pyexec,
                '-m',
                'spyder_kernels.console',
                '-f',
                '{connection_file}'
            ]

        logger.info('Kernel command: {}'.format(kernel_cmd))

        return kernel_cmd

    @property
    def env(self):
        """Env vars for kernels"""
        # Add our PYTHONPATH to the kernel
        pathlist = CONF.get('main', 'spyder_pythonpath', default=[])

        default_interpreter = CONF.get('main_interpreter', 'default')
        pypath = add_pathlist_to_PYTHONPATH([], pathlist, ipyconsole=True,
                                            drop_env=False)

        # Environment variables that we need to pass to our sitecustomize
        umr_namelist = CONF.get('main_interpreter', 'umr/namelist')

        if PY2:
            original_list = umr_namelist[:]
            for umr_n in umr_namelist:
                try:
                    umr_n.encode('utf-8')
                except UnicodeDecodeError:
                    umr_namelist.remove(umr_n)
            if original_list != umr_namelist:
                CONF.set('main_interpreter', 'umr/namelist', umr_namelist)

        env_vars = {
            'SPY_EXTERNAL_INTERPRETER': not default_interpreter,
            'SPY_UMR_ENABLED': CONF.get('main_interpreter', 'umr/enabled'),
            'SPY_UMR_VERBOSE': CONF.get('main_interpreter', 'umr/verbose'),
            'SPY_UMR_NAMELIST': ','.join(umr_namelist),
            'SPY_RUN_LINES_O': CONF.get('ipython_console', 'startup/run_lines'),
            'SPY_PYLAB_O': CONF.get('ipython_console', 'pylab'),
            'SPY_BACKEND_O': CONF.get('ipython_console', 'pylab/backend'),
            'SPY_AUTOLOAD_PYLAB_O': CONF.get('ipython_console',
                                             'pylab/autoload'),
            'SPY_FORMAT_O': CONF.get('ipython_console',
                                     'pylab/inline/figure_format'),
            'SPY_BBOX_INCHES_O': CONF.get('ipython_console',
                                          'pylab/inline/bbox_inches'),
            'SPY_RESOLUTION_O': CONF.get('ipython_console',
                                         'pylab/inline/resolution'),
            'SPY_WIDTH_O': CONF.get('ipython_console', 'pylab/inline/width'),
            'SPY_HEIGHT_O': CONF.get('ipython_console', 'pylab/inline/height'),
            'SPY_USE_FILE_O': CONF.get('ipython_console',
                                       'startup/use_run_file'),
            'SPY_RUN_FILE_O': CONF.get('ipython_console', 'startup/run_file'),
            'SPY_AUTOCALL_O': CONF.get('ipython_console', 'autocall'),
            'SPY_GREEDY_O': CONF.get('ipython_console', 'greedy_completer'),
            'SPY_JEDI_O': CONF.get('ipython_console', 'jedi_completer'),
            'SPY_SYMPY_O': CONF.get('ipython_console', 'symbolic_math'),
            'SPY_TESTING': running_under_pytest() or SAFE_MODE,
            'SPY_HIDE_CMD': CONF.get('ipython_console', 'hide_cmd_windows')
        }

        if self.is_pylab is True:
            env_vars['SPY_AUTOLOAD_PYLAB_O'] = True
            env_vars['SPY_SYMPY_O'] = False
            env_vars['SPY_RUN_CYTHON'] = False
        if self.is_sympy is True:
            env_vars['SPY_AUTOLOAD_PYLAB_O'] = False
            env_vars['SPY_SYMPY_O'] = True
            env_vars['SPY_RUN_CYTHON'] = False
        if self.is_cython is True:
            env_vars['SPY_AUTOLOAD_PYLAB_O'] = False
            env_vars['SPY_SYMPY_O'] = False
            env_vars['SPY_RUN_CYTHON'] = True

        # Add our PYTHONPATH to env_vars
        env_vars.update(pypath)

        # Making all env_vars strings
        clean_env_vars = clean_env(env_vars)

        return clean_env_vars
