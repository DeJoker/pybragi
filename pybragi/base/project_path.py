import os
import pandas as pd
import datetime


def get_project_path(project_name: str):
    project_root = os.path.join(os.path.expanduser('~'), project_name)
    os.makedirs(project_root, exist_ok=True)
    return project_root

PROJECT_ROOT = get_project_path(".bragi")
def register_project_root(project_name: str = ".bragi"):
    global PROJECT_ROOT
    PROJECT_ROOT = get_project_path(project_name)

# "%Y-%m-%dT%H-%M-%S"
def pandas_to_csv(df: pd.DataFrame, var_name: str, save_dir: str = "", strftime: str = "%Y-%m-%d"):
    global PROJECT_ROOT
    dir_csv = os.path.join(PROJECT_ROOT, os.path.basename(save_dir))
    os.makedirs(dir_csv, exist_ok=True)

    today = datetime.datetime.now().strftime(strftime)
    output_csv = os.path.join(dir_csv, f"{var_name}-{today}.csv")
    df.to_csv(output_csv, index=False) # 不包含自动生成的索引列
    print(f"save to {output_csv}")



if __name__ == "__main__":
    root = get_project_path()
    with open(os.path.join(root, "dasd.txt"), "w") as f:
        f.write("speek in English\n")
        f.write("让我们说中文\n")
    print(1)

