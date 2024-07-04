import os
import pandas as pd
from nptdms import TdmsFile

def merge_tdms_files(folder_path, output_file):
    # Read data from all TDMS files in the folder
    data_frames = []
    for file in os.listdir(folder_path):
        if file.endswith(".tdms"):
            tdms_file = TdmsFile.read(os.path.join(folder_path, file))
            for group in tdms_file.groups():
                group_data = group.as_dataframe()
                data_frames.append(group_data)
    
    # Concatenate all data frames
    merged_df = pd.concat(data_frames, axis=0, ignore_index=True)
    
    # Handle conflicting column names
    merged_df.columns = [f"{col_name}_{file_name}" if col_name in merged_df.columns.duplicated() else col_name for col_name, file_name in zip(merged_df.columns, os.listdir(folder_path))]
    
    # Convert merged TDMS to CSV
    merged_df.to_csv(output_file, index=False)
    
     # Write merged TDMS file
    merged_tdms_file = TdmsFile()
    for col in merged_df.columns:
        merged_tdms_file.write_segment(merged_df[col].values, col)
    merged_tdms_file.write(output_file.replace(".csv", ".tdms"))


# Usage example
folder_path = r"C:\Users\U436445\OneDrive - Danfoss\Documents\Codes\GUI\TDMS\TDMS"
output_file = os.path.join(folder_path, "merged_data.csv")
merge_tdms_files(folder_path, output_file)