from nptdms import TdmsFile
import pandas as pd
import os

# Read the TDMS file
#join with current path
file_path = os.path.join(os.getcwd(), "1_1.tdms")
tdms_file = TdmsFile.read(file_path)

# Convert TDMS data to a dictionary of DataFrames
data = {group.name: group.as_dataframe() for group in tdms_file.groups()}

# Display the data as an organized DataFrame
for group_name, df in data.items():
    print(f"Group: {group_name}")
    print(df)