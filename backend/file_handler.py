import os

UPLOAD_FOLDER = "uploads"

def allowed_file(filename):
    return filename.endswith(".csv")