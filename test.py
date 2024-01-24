from datetime import datetime
from config import *
import os




file_extension = ".bin"
current_date = datetime.now().strftime("%Y-%m-%d")
filepath = os.path.join(dir_path, f"{base_filename}_{current_date}{file_extension}")

print(filepath)