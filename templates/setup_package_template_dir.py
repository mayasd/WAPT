# -*- coding: utf-8 -*-
from setuphelpers import *
import re
import glob
import pefile
import os

uninstallkey = []

install_dir = '%(installer)s'
applabel = None

def is_x64(exefilename):
    with disable_file_system_redirection():
        pe = pefile.PE(exefilename,fast_load=True)
        try:
            if pe.FILE_HEADER.Machine == 0x8664:
                result = True
            else:
                result = False
        finally:
            # be sure to release exe
            pe.close()
        return result

def find_exes(root):
    """ Returns all .exe in root directory and subdirs"""
    result = []
    for entry in os.listdir(root):
        if os.path.isdir(entry):
            result.extend(find_exes(makepath(root,entry)))
        elif glob.fnmatch.fnmatch(entry,'*.exe'):
            result.append(makepath(root,entry))
    return result

def sort_path_length(exes):
    return sorted(exes,key=lambda a:len(os.path.splitext(a)))

def find_app(adir):
    exes = sorted(sort_path_length(find_exes(adir)),key = lambda a: -os.stat(a).st_size)
    return exes[0]

"""
Available template vars:
    packagename
    uninstallkey
    silentflags
    installer
    product
    description
"""

def install():
    global applabel

    app = find_app(install_dir)
    if is_x64(app):
        if not iswin64():
            error('The application {} is a x64 executable'.format(app))
        destdir = makepath(programfiles64,install_dir)
    else:
        destdir = makepath(programfiles32,install_dir)

    print('Installing %(packagename)s into {}'.format(destdir))
    mkdirs(destdir)

    copytree2(install_dir,destdir)
    if applabel is None:
        applabel = get_file_properties(app)['FileDescription'] or get_file_properties(app)['ProductName']

    if applabel is not None:
        create_programs_menu_shortcut('{}.lnk'.format(applabel),makepath(destdir,os.path.basename(app)))
    register_windows_uninstall(control)

def uninstall():
    global applabel
    if applabel is not None:
        remove_programs_menu_shortcut(applabel)
    unregister_uninstall(control.package)

