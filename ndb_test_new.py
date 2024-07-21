import sys
import os
import pandas as pd
import json
import numpy as np
from scipy.signal import find_peaks, peak_prominences, savgol_filter
from nptdms import TdmsFile
import matplotlib.pyplot as plt
from multiprocessing import Pool, cpu_count


def clean_column_names(df):
    df.columns = df.columns.str.replace("/", "")
    df.columns = df.columns.str.replace("'", "")
    df.columns = df.columns.str.replace("Data", "")
    return df

def process_tdms_folder(folder_path):
    tdms_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith('.tdms')]
    data = {}
    
    for file_path in tdms_files:
        try:
            tdms_file = TdmsFile.read(file_path)
            df = tdms_file.as_dataframe()
            df = df.dropna(axis=1, how='all')
            df = clean_column_names(df)
            data[os.path.basename(file_path)] = df.to_dict(orient='split')
        except Exception as e:
            print(json.dumps({"error": f"Error reading {file_path}: {str(e)}"}))
            if not data:
                raise e
    return data

def neutral_deadband_test(df, file):
    derivative = savgol_filter(df['HST_output_RPM'], 1751, 3, 2)
    peak_indices, _ = find_peaks(derivative)
    peak_proms = peak_prominences(derivative, peak_indices)[0]
    sorted_peak_indices = peak_indices[np.argsort(peak_proms)]
    top_40_percent = int(0.75 * len(sorted_peak_indices))
    highest_peaks = sorted_peak_indices[-top_40_percent:]

    threshold_val = df['HST_output_RPM'].max() // 100
    df_new = pd.DataFrame()
    df_new['Time'] = df['Time'].iloc[highest_peaks][df['HST_output_RPM'].iloc[highest_peaks] < threshold_val]
    df_new['Derivative'] = derivative[highest_peaks][df['HST_output_RPM'].iloc[highest_peaks] < threshold_val]
    df_new['HST_output_RPM'] = df['HST_output_RPM'].iloc[highest_peaks][df['HST_output_RPM'].iloc[highest_peaks] < threshold_val]
    df_new = df_new.sort_values('Time')

    df_4pt = pd.DataFrame()
    mid_time = df_new['Time'].max() / 2
    first_half = df_new[df_new['Time'] <= mid_time]
    second_half = df_new[df_new['Time'] > mid_time]
    min_max_first_half = first_half.loc[[first_half['Time'].idxmin(), first_half['Time'].idxmax()]]
    min_max_second_half = second_half.loc[[second_half['Time'].idxmin(), second_half['Time'].idxmax()]]
    df_4pt = pd.concat([df_4pt, min_max_first_half, min_max_second_half])

    ndb_df = pd.DataFrame(
        columns=["Input RPM", "HST_output_RPM", "A1", "A2", "B1", "B2", "Swash Angle Total Band", "A band", "B band",
                 "Zero of NDB lies at", "Delta @ A1", "Delta @ A2", "Delta @ B1", "Delta @ B2", "Time @ A1",
                 "Time @ A2", "Time @ B1", "Time @ B2"])

    input_rpm = os.path.splitext(os.path.basename(file))[0]
    hst_output_rpm = df_4pt['HST_output_RPM'].mean()

    merged_df = df_4pt.merge(df[['Swash_Angle', 'Delta']], left_index=True, right_index=True)
    A1_swash_angle = min(merged_df.iloc[0]['Swash_Angle'], merged_df.iloc[3]['Swash_Angle'])
    A2_swash_angle = max(merged_df.iloc[0]['Swash_Angle'], merged_df.iloc[3]['Swash_Angle'])
    B1_swash_angle = max(merged_df.iloc[1]['Swash_Angle'], merged_df.iloc[2]['Swash_Angle'])
    B2_swash_angle = min(merged_df.iloc[1]['Swash_Angle'], merged_df.iloc[2]['Swash_Angle'])

    A1_delta = merged_df[merged_df['Swash_Angle'] == A1_swash_angle]['Delta'].values[0]
    A2_delta = merged_df[merged_df['Swash_Angle'] == A2_swash_angle]['Delta'].values[0]
    B1_delta = merged_df[merged_df['Swash_Angle'] == B1_swash_angle]['Delta'].values[0]
    B2_delta = merged_df[merged_df['Swash_Angle'] == B2_swash_angle]['Delta'].values[0]

    A1_time = merged_df[merged_df['Swash_Angle'] == A1_swash_angle]['Time'].values[0]
    A2_time = merged_df[merged_df['Swash_Angle'] == A2_swash_angle]['Time'].values[0]
    B1_time = merged_df[merged_df['Swash_Angle'] == B1_swash_angle]['Time'].values[0]
    B2_time = merged_df[merged_df['Swash_Angle'] == B2_swash_angle]['Time'].values[0]

    swash_angle_tot_band = A1_swash_angle - B1_swash_angle
    a_band = abs(A1_swash_angle - A2_swash_angle)
    b_band = abs(B1_swash_angle - B2_swash_angle)
    zero_of_ndb = A1_swash_angle - (swash_angle_tot_band / 2)

    ndb_df.loc[0] = [
        input_rpm, hst_output_rpm, A1_swash_angle, A2_swash_angle, B1_swash_angle, B2_swash_angle,
        swash_angle_tot_band, a_band, b_band, zero_of_ndb, A1_delta, A2_delta, B1_delta, B2_delta,
        A1_time, A2_time, B1_time, B2_time
    ]

    return ndb_df, df_new, df_4pt, merged_df

def plot_peaks(df, file):
    
    plots = {}
    
    derivative = savgol_filter(df['HST_output_RPM'], 1751, 3, 2)
    peak_indices, _ = find_peaks(derivative)
    peak_proms = peak_prominences(derivative, peak_indices)[0]
    sorted_peak_indices = peak_indices[np.argsort(peak_proms)]
    top_10_percent = int(0.75 * len(sorted_peak_indices))
    highest_peaks = sorted_peak_indices[-top_10_percent:]

    ndb_df, df_new, df_4pt, merged_df = neutral_deadband_test(df, file)
    
    fig, axes = plt.subplots(3, 1, figsize=(24, 28))

    # Plot 1: Derivative
    axes[0].plot(df['Time'], derivative, label='Derivative')
    axes[0].plot(df_4pt['Time'], df_4pt['Derivative'], 'ro', alpha=0.8, markersize=3)
    axes[0].set_title(f'Derivative Plot - {file}')
    axes[0].set_xlabel('Time')
    axes[0].set_ylabel('Derivative')
    axes[0].legend()

    # Plot 2: HST Output RPM
    axes[1].plot(df['Time'], df['HST_output_RPM'], label='HST_output_RPM')
    axes[1].plot(df_4pt['Time'], df_4pt['HST_output_RPM'], 'ro', alpha=0.8, markersize=3)
    axes[1].set_title(f'HST Output RPM - {file}')
    axes[1].set_xlabel('Time')
    axes[1].set_ylabel('HST Output RPM')
    axes[1].legend()

    # Plot 3: Swash Angle
    axes[2].plot(df['Time'], df['Swash_Angle'], label='Swash Angle')
    axes[2].plot(merged_df['Time'], merged_df['Swash_Angle'], 'ro', alpha=0.8, markersize=3)
    axes[2].set_title(f'Swash Angle - {file}')
    axes[2].set_xlabel('Time')
    axes[2].set_ylabel('Swash Angle')
    axes[2].legend()

    plt.tight_layout()
    plot_path = f'combined_plots_{file}.png'
    plt.savefig(plot_path, dpi=500, bbox_inches='tight')
    plt.close(fig)

    plots['combined'] = {
        'path': plot_path,
        'title': f'Combined Plots - {file}',
        'subtitles': [
            f'Derivative Plot - {file}',
            f'HST Output RPM - {file}',
            f'Swash Angle - {file}'
        ]
    }

    return plots, merged_df

def main(folder_path):
    try:
        data = process_tdms_folder(folder_path)
    except Exception as e:
        print(json.dumps({"error": f"Error processing folder: {str(e)}"}))
        return

    all_results = {
        'tables': {},
        'plots': {}
    }

    for file_name, df_dict in data.items():
        try:
            
            df = pd.DataFrame(**df_dict)
            if df.empty:
                print(json.dumps({"warning": f"Empty DataFrame for {file_name}"}))
                continue

            ndb_df, df_new, df_4pt, merged_df = neutral_deadband_test(df, file_name)
            if ndb_df is not None and not ndb_df.empty:
                output_csv = os.path.join(folder_path, f'Neutral_Deadband_Results_{file_name}.csv')
                ndb_df.to_csv(output_csv, index=False)
                all_results['tables'][file_name] = ndb_df.to_dict(orient='split')

            plot_data, merged_df = plot_peaks(df, file_name)
            if plot_data is not None and merged_df is not None:
                all_results['tables'][f'Merged Data {file_name}'] = merged_df.to_dict(orient='split')
                all_results['plots'][file_name] = plot_data #plot+data
        except Exception as e:
            print(json.dumps({"error": f"Error processing file {file_name}: {str(e)}"}))
            continue

    if not all_results['tables'] and not all_results['plots']:
        print(json.dumps({"error": "No valid results were generated."}))
        return

    print(json.dumps(all_results))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
        main(folder_path)
    else:
        print(json.dumps({"error": "Please provide the TDMS folder path as an argument."}))