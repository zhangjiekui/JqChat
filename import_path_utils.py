import os, sys,pathlib    
def add_import_paths():
    project_root_path = pathlib.Path().resolve()
    p1 = project_root_path/'jqcode'
    p2 = project_root_path/'jqchatweb'
    p3 = project_root_path/'JqR2R'
    p4 = project_root_path/'JqR2R/py/core'
    p5 = project_root_path/'JqR2R/py/sdk'
    p6 = project_root_path/'JqR2R/py/shared'

    for p in [project_root_path, p1, p2]:
        sys.path.append(str(p))
    print(sys.path)
added_paths = add_import_paths()

# nano ~/.bashrc
# export PYTHONPATH=$PYTHONPATH:/data/projects/JqChat:/data/projects/JqChat/jqcode:/data/projects/JqChat/jqchatweb
