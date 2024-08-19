import os, sys,pathlib    
def add_import_paths():
    project_root_path = pathlib.Path().resolve()
    p1 = project_root_path/'jqcode'
    p2 = project_root_path/'jqchatweb'
    for p in [project_root_path, p1, p2]:
        sys.path.append(str(p))
    print(sys.path)
added_paths = add_import_paths()

# nano ~/.bashrc
# export PYTHONPATH=$PYTHONPATH:/data/projects/JqChat:/data/projects/JqChat/jqcode:/data/projects/JqChat/jqchatweb
