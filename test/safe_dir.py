

import os
import shutil

WORKING_DIR = "test_dir"
shutil.rmtree(WORKING_DIR, ignore_errors=True)

os.makedirs(WORKING_DIR, exist_ok=True)








