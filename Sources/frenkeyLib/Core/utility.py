import difflib
import os
import re

import PySystem
from urllib import parse

import Py4GW

##TODO: Make this more robust to handle different parent folder names
def GetPy4GWPath() -> str:
        file_path = PySystem.Console.get_projects_path()
        marker = os.sep + "Py4GW" + os.sep
        base_path = file_path.partition(marker)[0] + marker if marker in file_path else file_path

        return base_path

@staticmethod
def string_similarity(a: str, b: str) -> float:
    """
    Returns similarity ratio between two strings (0.0 to 1.0).
    """
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

@staticmethod            
def get_image_name(url: str) -> str:
    # Extract the last part of the URL (the filename)
    last_part = url.rsplit('/', 1)[-1]

    # Remove "File:" prefix if present
    last_part = last_part.replace("File:", "")

    # Remove px size prefix like "134px-"
    last_part = re.sub(r'^\d+px-', '', last_part)
    last_part = last_part.replace("%22", "")  # Remove URL-encoded quotes

    # Decode URL-encoded characters
    decoded = parse.unquote(last_part)

    decoded = decoded.replace("_", " ")  # Replace spaces with underscores

    # Allow characters valid on most filesystems: keep letters, numbers, spaces, underscores,
    # dashes, apostrophes, parentheses, and periods
    # Replace only truly invalid characters with underscore
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', decoded)

    # Replace multiple underscores with one (optional cleanup)
    sanitized = re.sub(r'_+', '_', sanitized)

    # Strip leading/trailing spaces/underscores
    return sanitized.strip(" _")
    
# ImGuiIniReader removed: it only re-read window pos/size/collapsed from ImGui's own
# imgui.ini to force geometry back onto windows. Window placement is now delegated
# entirely to ImGui's native persistence, so this reader is obsolete.
