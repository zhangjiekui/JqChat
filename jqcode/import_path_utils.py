import os, sys,pathlib    
def add_import_paths():
    project_root_path = pathlib.Path().resolve()
    p1 = project_root_path/'jqcode'
    p2=project_root_path/'kernel_program'
    p3=project_root_path/'web'
    for p in [project_root_path, p1,p2,p3]:
        if str(p) not in sys.path: 
            sys.path.append(str(p))
added_paths = add_import_paths()
