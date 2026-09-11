import os

from file_reader import read_file, get_file_info


# ============================================================
# PHASE 5.4.1 — ADVANCED FILE MANAGER
# ============================================================

current_file = None
uploaded_files = {}


# ============================================================
# SET CURRENT FILE
# ============================================================

def set_current_file(file_path):
    global current_file

    if not file_path:
        raise ValueError("File path is required.")

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    current_file = file_path

    filename = os.path.basename(file_path)
    uploaded_files[filename] = file_path

    print("📁 Current file:", filename)

    return file_path


# ============================================================
# GET CURRENT FILE
# ============================================================

def get_current_file():
    return current_file


def get_current_file_data():
    if current_file is None:
        return None

    return read_file(current_file)


# ============================================================
# ADD / UPLOAD FILE
# ============================================================

def add_file(file_path):
    if not file_path:
        raise ValueError("File path is required.")

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    filename = os.path.basename(file_path)

    uploaded_files[filename] = file_path

    # New upload automatically becomes current
    set_current_file(file_path)

    print("✅ File added:", filename)

    return {
        "success": True,
        "filename": filename,
        "path": file_path
    }


# ============================================================
# GET ALL UPLOADED FILES
# ============================================================

def get_uploaded_files():
    return uploaded_files.copy()


def get_file_count():
    return len(uploaded_files)


# ============================================================
# GET FILE BY NAME
# ============================================================

def get_file(filename):
    if not filename:
        return None

    # Exact filename
    if filename in uploaded_files:
        return uploaded_files[filename]

    # Case-insensitive filename search
    filename_lower = filename.lower().strip()

    for name, path in uploaded_files.items():

        if name.lower().strip() == filename_lower:
            return path

    return None


# ============================================================
# GET FILE DATA BY NAME
# ============================================================

def get_file_data(filename):

    file_path = get_file(filename)

    if file_path is None:
        return None

    return read_file(file_path)


# ============================================================
# GET TWO FILES FOR COMPARISON
# ============================================================

def get_comparison_files(file1, file2):

    path1 = get_file(file1)
    path2 = get_file(file2)

    if path1 is None or path2 is None:
        return None

    return {
        "file1": path1,
        "file2": path2
    }


# ============================================================
# REMOVE FILE
# ============================================================

def remove_file(filename):
    global current_file

    if filename not in uploaded_files:
        return False

    file_path = uploaded_files.pop(filename)

    if current_file == file_path:
        current_file = None

    return True


# ============================================================
# CLEAR ALL FILES
# ============================================================

def clear_files():
    global current_file

    uploaded_files.clear()
    current_file = None

    print("🧹 File manager cleared.")


# ============================================================
# CURRENT FILE INFO
# ============================================================

def get_current_file_info():

    if current_file is None:
        return None

    return get_file_info(current_file)


# ============================================================
# FILE TYPE
# ============================================================

def get_file_type(file_path):

    if not file_path:
        return None

    return os.path.splitext(file_path)[1].lower()


# ============================================================
# SUPPORTED FILE CHECK
# ============================================================

def is_supported_file(file_path):

    supported_extensions = {
        ".csv",
        ".xlsx",
        ".xls",
        ".json",
        ".pdf",
        ".docx",
        ".pptx"
    }

    return get_file_type(file_path) in supported_extensions


# ============================================================
# MANAGER STATUS
# ============================================================

def manager_status():

    return {
        "current_file": (
            os.path.basename(current_file)
            if current_file
            else None
        ),

        "file_count": get_file_count(),

        "files": list(uploaded_files.keys())
    }