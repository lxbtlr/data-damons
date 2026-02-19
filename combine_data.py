import argparse
import pandas as pd
import re
from pathlib import Path

"""
Quick and dirty perf csv parser + run_tpch parser. 

Point this at output folder for a hi_res_<>.sh run.

Expects the folder to be of the format <machine>_<compiler>_...

Currently requires you to manually append data together

ツ

"""
def parse_perf_semicolon_format(file_path):
    """
    Parses a semicolon-delimited perf data file into a dictionary of metrics.

    Reads a file where metrics are separated by ';' characters. It cleans 
    numeric strings (removing '<not supported>' and non-numeric artifacts) 
    and maps the third column (metric name) to the first column (value).

    params :

    file_path - STR The path to the .data file to be parsed.

    returns :

    metrics - DICT A dictionary mapping metric names to float values or None.

    """
    metrics = {}
    try:
        with open(file_path, 'r') as f:
            for line in f:
                parts = [p.strip().replace("'", "") for p in line.split(';')]
                if len(parts) >= 3:
                    val_str = parts[0]
                    metric_name = parts[2]
                    
                    if val_str == "<not supported>" or not val_str:
                        metrics[metric_name] = None
                    else:
                        try:
                            metrics[metric_name] = float(val_str)
                        except ValueError:
                            metrics[metric_name] = None
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return metrics

def build_combined_dataframe(directory):
    """
    Combines CSV execution times and perf metrics, including machine name from the folder.


    Scans a directory for CSV/data pairs. It extracts the machine name from the 
    provided directory string and attaches it to every parsed record.

    params :

    directory - STR The directory containing both .csv and .data files.

    returns :

    df - DATAFRAME A pandas DataFrame containing metadata, machine name, and metrics.

    """
    base_path = Path(directory).resolve()
    pieces = base_path.name.split("_")  # Extracts the final folder name as machine name
    machine_name = pieces[0]
    compiler = pieces[1]
    # Regex for filename: r<rep>_<query><engine>_t<threads>
    filename_re = re.compile(r"r(\d+)_(\d+)([hv])_t(\d+)")
    
    rows = []
    
    for csv_file in base_path.glob("*.csv"):
        match = filename_re.match(csv_file.stem)
        if not match:
            continue
            
        rep, q_num, eng, threads = match.groups()
        
        # Parse main CSV
        try:
            # skiprows=1 skips the header row
            csv_data = pd.read_csv(csv_file, header=None, skipinitialspace=True, skiprows=1)
            if not csv_data.empty:
                execution_time = float(csv_data.iloc[0, 1]) 
                query_label = str(csv_data.iloc[0, 0]).strip()
            else:
                execution_time, query_label = None, None
        except Exception:
            execution_time, query_label = None, None

        # Parse corresponding .data file
        perf_file = base_path / f"{csv_file.stem}.data"
        perf_data = parse_perf_semicolon_format(perf_file) if perf_file.exists() else {}

        # Consolidate row data
        row = {
            'machine': machine_name,
            'compiler': compiler,
            'repetition': int(rep),
            'query': int(q_num),
            'engine': 'vectorwise' if eng == 'v' else 'hyper',
            'threads': int(threads),
            'query_label': query_label,
            'time': execution_time
        }
        row.update(perf_data)
        rows.append(row)
        
    return pd.DataFrame(rows)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse perf/CSV data with machine name extraction.")
    parser.add_argument("dir", type=str, help="Directory containing .csv and .data files.")
    parser.add_argument("-o", "--output", type=str, default="combined_results.csv", 
                        help="Output filename (default: combined_results.csv)")
    # New append flag
    parser.add_argument("-a", "--append", action="store_true", 
                        help="Append to the output CSV if it already exists.")
    
    args = parser.parse_args()
    output_path = Path(args.output)
    
    print(f"Parsing data for machine: {Path(args.dir).resolve().name}")
    new_df = build_combined_dataframe(args.dir)
    
    if not new_df.empty:
        # Check if we should append to an existing file
        if args.append and output_path.exists():
            print(f"Appending to existing file: {output_path}")
            try:
                existing_df = pd.read_csv(output_path)
                # Concat handles missing columns gracefully if metrics differ between runs
                final_df = pd.concat([existing_df, new_df], ignore_index=True)
            except pd.errors.EmptyDataError:
                # Fallback if the existing file is completely empty
                final_df = new_df
        else:
            final_df = new_df

        # Ensure the final output remains cleanly sorted
        final_df = final_df.sort_values(by=['machine', 'query', 'threads', 'repetition'])
        
        final_df.to_csv(output_path, index=False)
        print(f"Success! Exported {len(new_df)} new rows. Total rows in file: {len(final_df)}")
    else:
        print("No valid file pairs found.")
