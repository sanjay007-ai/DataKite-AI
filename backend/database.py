import pandas as pd

data = pd.DataFrame()

def load_data(file_path):
    global data
    data = pd.read_csv(file_path)
    return data