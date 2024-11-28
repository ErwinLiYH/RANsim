# %%
import os
import yaml

# %%
base_path = "../exps"
base_name = "exp"

# %%
infos = {}

for name in os.listdir(base_path):
    if name.startswith(base_name):
        order = int(name.lstrip(base_name))
        info_path = os.path.join(base_path, name, "info.yaml")
        if os.path.exists(info_path):
            with open(info_path, "r") as file:
                info = yaml.safe_load(file)
        else:
            info = {}
        infos[order] = info

infos = dict(sorted(infos.items()))
infos = {k:v for k,v in infos.items() if v != {}}
infos

# %%
with open(os.path.join(base_path, "aaa_infos.yaml"), "w") as file:
    yaml.safe_dump(infos, file)