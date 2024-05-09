import os
from typing import List
import argparse

def generate_env_script(ns_build_root:str, ld_preload_paths : List[str] = None, shell_path : str = "set_environment.sh"):
    bindings_path = os.path.join(ns_build_root, "bindings/python")
    lib_path = os.path.join(ns_build_root, "lib")
    include_path = os.path.join(ns_build_root, "include")

    script_content = f"""#!/bin/bash
export PYTHONPATH={bindings_path}:$PYTHONPATH
export PATH={lib_path}:$PATH
export LD_LIBRARY_PATH={include_path}:$LD_LIBRARY_PATH
"""

    if ld_preload_paths:
        ld_preload_string = os.pathsep.join(ld_preload_paths)
        script_content += f"\nexport LD_PRELOAD={ld_preload_string}:$LD_PRELOAD\n"

    with open(shell_path, "w") as file:
        file.write(script_content)

    print(f"Shell script '{shell_path}' has been created.")

def main():
    parser = argparse.ArgumentParser(description="Generate shell script to set environment variables for ns-3")
    parser.add_argument("ns_build_root", type=str, help="Path to ns-3 build root directory")
    parser.add_argument("--ld_preload_paths", "-l", type=str, nargs="+", help="List of paths to be added to LD_PRELOAD")
    parser.add_argument("--shell_path", "-p", type=str, default="set_environment.sh", help="Path to the shell script to be generated")
    args = parser.parse_args()

    generate_env_script(args.ns_build_root, args.ld_preload_paths, args.shell_path)
