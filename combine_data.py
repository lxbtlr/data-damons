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

def parse_perf_stats_format(file_path):
    """
    Parses a standard perf stats output file into a dictionary of metrics.


    Reads a file containing hardware counters and time elapsed metrics, ignoring headers and extracting numeric values. Commas in numbers are removed, and time metrics are normalized to include '_seconds' in their names.

    params :

    file_path - STR The path to the .stats file to be parsed.

    returns :

    metrics - DICT A dictionary mapping metric names to float values.

    """
    metrics = {}
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                #print(line, end="")
                # Skip empty lines, comments, and headers
                if not line or line.startswith('#') or line.startswith('Performance'):
                    continue

                parts = line.split()
                if len(parts) >= 2:
                    #print(f": parts ({parts})",end="")
                    # Remove commas from the numeric value string
                    val_str = parts[0].replace(',', '')
                    try:
                        val = float(val_str)
                        if parts[1] == 'seconds':
                            #print(": Skipping")
                            continue
                            metric_name = "_".join(parts[2:]) + "_seconds"
                        else:
                            metric_name = parts[1]

                        #print(f":setting {metric_name}:{val}")
                        metrics[metric_name] = val
                    except ValueError:
                        # If the first string is not a number, skip the line safely
                        #print(": Skipping")
                        continue
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
    vec_sweep = False
    base_path = Path(directory).resolve()
    pieces = base_path.name.split("_")  # Extracts the final folder name as machine name
    machine_name = pieces[0]
    compiler = pieces[1]
    # Regex for filename: r<rep>_<query><engine>_t<threads>
    #filename_re = re.compile(r"r(\d+)_(\d+)([hv])_t(\d+)")
    
    # now includes vectorsize
    if vec_sweep:
        filename_re = re.compile(r"r(\d+)_(\d*?)_(\d+)([hv])_t(\d+)")
    else:
        filename_re = re.compile(r"r(\d+)_(\d+)([hv])_t(\d+)") #r(\d+)_(\d*?)_(\d+)([hv])_t(\d+)")

    rows = []
    for csv_file in base_path.glob("*.csv"):
        match = filename_re.match(csv_file.stem)
        if not match:
            continue
            
        if vec_sweep:
            rep, vec_size, q_num, eng, threads = match.groups()

            if vec_size == "":
                vec_size = 0
        else:
            rep, q_num, eng, threads = match.groups()
        # Parse main CSV
        try:
            # skiprows=1 skips the header row



            csv_data = pd.read_csv(csv_file, names=["name","time","CPUs","IPC",
                                                    "GHz","Bandwidth","cycles",
                                                    "LLC-misses", "l1-misses",   
                                                    "l1-hits","instr.",
                                                    "br. misses","task-clock"], 
                                   skipinitialspace=True, index_col=False,skiprows=1)
            if not csv_data.empty:
                execution_time = float(csv_data["time"].iloc[0])

                query_label = str(csv_data["name"].iloc[0]).strip()

                query_freq = float(csv_data["GHz"].iloc[0])
                ipc = str(csv_data["IPC"].iloc[0]).strip()
                
                DEBUG_MODE=False
                if DEBUG_MODE:
                    print(csv_file)
                    print(csv_data)
                    print(csv_data["GHz"].values[0])

                    print(execution_time)
                    print(query_freq)
                    print(query_label)
                    print(ipc)

                #execution_time = float(csv_data.iloc[0, 1]) 
                #query_label = str(csv_data.iloc[0, 0]).strip()
                
            else:
                print("exception path")
                raise Exception
                execution_time, query_label = None, None
                ipc = None
                query_freq = None

        except Exception:
            execution_time, query_label = None, None
            ipc = None
            query_freq = None

        # Parse corresponding .data file
        perf_file = base_path / f"{csv_file.stem}.data"
        perf_data = parse_perf_semicolon_format(perf_file) if perf_file.exists() else {}

        # Parse corresponding .stats file
        stats_file = base_path / f"{csv_file.stem}.stats"
        stats_data = parse_perf_stats_format(stats_file) if stats_file.exists() else {}
        try:
            est = stats_data["LLC-misses"] / stats_data["cycle_activity.stalls_l3_miss"]
            #print(f'{stats_data["LLC-misses"]} / {stats_data["cycle_activity.stalls_l3_miss"]}=\n\t\t{est}')
        except KeyError:
            print(f"empty/broken file: {csv_file}")
            est = -1 

        # Consolidate row data
    
        row = {
            'machine': machine_name,
            'compiler': compiler,
            'avg_freq': query_freq,
            'ipc': ipc,
            'repetition': int(rep),
            'query': int(q_num),
            'engine': 'vectorwise' if eng == 'v' else 'hyper',
            'threads': int(threads),
            'query_label': query_label,
            'time': execution_time
        }
        if vec_sweep:
            row["vectorsize"] = int(vec_size)
        
        row.update(perf_data)
        row.update(stats_data)
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
