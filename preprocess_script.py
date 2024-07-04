import pandas as pd

def preprocess_tdms_file(file_path):
    # Read the TDMS file
    tdms_data = pd.read_csv(file_path)

    # Convert float datetime/timestamp values to date time format
    tdms_data['Timestamp'] = pd.to_datetime(tdms_data['Timestamp'], unit='s') - pd.Timedelta(seconds=0.004)

    # Perform any other preprocessing steps here

    # Save the preprocessed data back to a CSV file
    preprocessed_file_path = file_path.replace('.tdms', '_preprocessed.csv')
    tdms_data.to_csv(preprocessed_file_path, index=False)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: preprocess_script.py <file_path>")
    else:
        file_path = sys.argv[1]
        preprocess_tdms_file(file_path)