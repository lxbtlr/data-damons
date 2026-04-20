import os
from dataclasses import dataclass, field
from typing import List

# Assuming range_test is a local python file/module in the same directory
import range_test 

@dataclass
class CompilerProfile:
    """
    Stores compiler-specific configurations for a given architecture.


    params :

    name - <str> The common name of the compiler (e.g., 'gcc', 'clang').
    c_bin - <str> The C compiler binary (e.g., 'gcc', 'clang-18').
    cxx_bin - <str> The C++ compiler binary (e.g., 'g++', 'clang++-18').
    arch_flags - <str> Architecture-specific compilation flags.

    returns :

    self - <CompilerProfile> The initialized dataclass instance.
    """
    name: str
    c_bin: str
    cxx_bin: str
    arch_flags: str

    def __str__(self) -> str:
        """
        Returns a succinct string representation of the compiler profile.


        Truncates the architecture flags if they are longer than 30 characters
        to prevent log spamming.

        params :

        returns :

        summary - <str> A condensed string representation of the instance.
        """
        flags_preview = f"{self.arch_flags[:30]}..." if len(self.arch_flags) > 30 else self.arch_flags
        return f"CompilerProfile(name='{self.name}', c_bin='{self.c_bin}', cxx_bin='{self.cxx_bin}', flags='{flags_preview}')"

    __repr__ = __str__


@dataclass
class MachineProfile:
    """
    Stores machine-specific configuration for benchmark testing.


    params :

    name - <str> The identifier for the machine (e.g., 'manchego', 'burrata').
    max_threads - <int> The maximum number of hardware threads available.
    thread_schedule - <List[int]> The specific interleaved order of threads to test.
    compilers - <List[CompilerProfile]> A list of available compiler profiles for this machine.
    base_build_dir - <str> The root directory for CMake builds.
    base_results_dir - <str> The root directory for outputting benchmark data.

    returns :

    self - <MachineProfile> The initialized dataclass instance.
    """
    name: str
    max_threads: int
    thread_schedule: List[int]
    compilers: List[CompilerProfile] = field(default_factory=list)
    base_build_dir: str = "$HOME/swole/db-engines/build"
    base_results_dir: str = "/tank/project/swole/hi_res"

    def __str__(self) -> str:
        """
        Returns a succinct string representation of the machine profile.


        Summarizes lists by showing their lengths and lists the compiler names
        instead of full compiler profiles.

        params :

        returns :

        summary - <str> A condensed string representation of the instance.
        """
        threads_preview = f"[{len(self.thread_schedule)} t. confs]"
        compilers_preview = f"[{', '.join(c.name for c in self.compilers)}]"
        return f"MachineProfile(name='{self.name}', max_threads={self.max_threads}, sched={threads_preview}, compilers={compilers_preview})"

    __repr__ = __str__

@dataclass
class ExperimentConfig:
    """
    Stores global, machine-independent configuration for an experiment.


    params :

    name - <str> The name of the experiment, used to isolate builds and results.
    scale_factor - <str> The scale factor directory for the dataset (e.g., 'sf100').
    queries - <List[int]> The list of specific queries to execute.
    vector_sizes - <List[int]> The list of vector sizes to test.
    reps - <int> The number of internal repetitions for the benchmark tool.
    mreps - <int> The number of macro repetitions (outer loop) for the script.

    returns :

    self - <ExperimentConfig> The initialized dataclass instance.
    """
    name: str
    scale_factor: str
    queries: List[int]
    vector_sizes: List[int]
    reps: int
    mreps: int
    enable_textme: bool = True

    def __str__(self) -> str:
        """
        Returns a succinct string representation of the experiment configuration.


        Summarizes lists like queries and vector sizes by showing their element counts.

        params :

        returns :

        summary - <str> A condensed string representation of the instance.
        """
        queries_preview = f"[{len(self.queries)} queries]"
        vs_preview = f"[{min(self.vector_sizes)}-{max(self.vector_sizes)}, {len(self.vector_sizes)} vs. confs]"
        return f"ExperimentConfig(name='{self.name}', sf='{self.scale_factor}', queries={queries_preview}, vectors={vs_preview}, reps={self.reps}, mreps={self.mreps})"

    __repr__ = __str__

def generate_benchmark_script(machine: MachineProfile, experiment: ExperimentConfig, output_path: str = None, make_dirs=False) -> bool:
    """
    Generates a tailored bash script for compiling and running a benchmark.


    params :

    machine - <MachineProfile> The profile containing architecture-specific configuration.
    experiment - <ExperimentConfig> The global configuration parameters for the benchmark.
    output_path - <str> Optional. The file path where the script will be saved. 

    returns :

    success - <bool> True if the script was generated successfully.
    """
    
    if output_path is None:
        output_path = f"run_{machine.name}_{experiment.name}.sh"

    # Define absolute paths for Slurm since it cannot evaluate bash variables in #SBATCH headers
    slurm_output_dir = f"{machine.base_results_dir}/{experiment.scale_factor}/{experiment.name}"
    
    # Pre-create the directory so Slurm doesn't silently fail to write the .out/.err logs
    if make_dirs:
        os.makedirs(slurm_output_dir, exist_ok=True)

    compiler_names = " ".join([f'"{c.name}"' for c in machine.compilers])
    
    compiler_bash_logic = ""
    for i, comp in enumerate(machine.compilers):
        condition = "if" if i == 0 else "elif"
        compiler_bash_logic += f"""
        {condition} [ "$compiler" == "{comp.name}" ]; then
            C_BIN="{comp.c_bin}"
            CXX_BIN="{comp.cxx_bin}"
            ARCH_FLAGS="{comp.arch_flags}" """
    compiler_bash_logic += "\n        else\n            echo \"Unknown compiler: $compiler\"; exit 1;\n        fi"

    # Format lists into space-separated strings for bash arrays
    textme_cmd = '"/tank/project/text/text-alex"' if experiment.enable_textme else '"echo"'

    threads_str = " ".join(map(str, machine.thread_schedule))
    queries_str = " ".join(map(str, experiment.queries))
    vectorsizes_str = " ".join(map(str, experiment.vector_sizes))

    script_content = f"""#!/bin/bash
#SBATCH --job-name={machine.name}_{experiment.name}
#SBATCH --output={slurm_output_dir}/{machine.name}_{experiment.name}_%j.out
#SBATCH --error={slurm_output_dir}/{machine.name}_{experiment.name}_%j.err
#SBATCH --exclusive

set -e
cd $HOME
machine="{machine.name}"

EXPERIMENT_NAME="{experiment.name}"
SCALE_FACTOR="{experiment.scale_factor}"
TEXTME={textme_cmd}

COMPILERS=({compiler_names})

# Isolate build directory by experiment name
BUILD_DIR="{machine.base_build_dir}/${{EXPERIMENT_NAME}}"

mkdir -p "$BUILD_DIR"

echo "========================================"
echo "PHASE 1: BUILD KERNELS"
echo "========================================"

pushd "$BUILD_DIR"

for compiler in "${{COMPILERS[@]}}"; do
    echo "Building for $compiler..."
    {compiler_bash_logic}
     
    COMMON_FLAGS="-O3 -fPIC -Wall -Wextra -Wno-unknown-pragmas"
    BASE_CXX_FLAGS="-std=c++17"
    BASE_C_FLAGS="-fdiagnostics-color"
    
    FINAL_CXX_FLAGS="$COMMON_FLAGS $BASE_CXX_FLAGS $ARCH_FLAGS"
    FINAL_C_FLAGS="$COMMON_FLAGS $BASE_C_FLAGS $ARCH_FLAGS"
    
    rm -rf CMakeCache.txt CMakeFiles/

    cmake ../.. \\
          -DCMAKE_C_COMPILER="$C_BIN" \\
          -DCMAKE_CXX_COMPILER="$CXX_BIN" \\
          -DCMAKE_CXX_FLAGS="$FINAL_CXX_FLAGS" \\
          -DCMAKE_C_FLAGS="$FINAL_C_FLAGS" \\
          -DCMAKE_BUILD_TYPE=Release || {{ echo "CMAKE failed for $compiler"; $TEXTME "failed in compilation"; exit 1; }}
          
    make run_tpch -j$(nproc) || {{ echo "MAKE failed for $compiler"; $TEXTME "failed in compilation"; exit 1; }}
    
    mv run_tpch "run_tpch_$compiler"
    echo "Created run_tpch_$compiler"
done

# Isolate results directory by scale factor and experiment name
RESULTS_BASE="{slurm_output_dir}"

echo "========================================"
echo "PHASE 2: DIRECT EXECUTION (UNROLLED)"
echo "========================================"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
#DATA_DIR="/tank/alexb/swole/tpch/${{SCALE_FACTOR}}/"
DATA_DIR="/vol/${{SCALE_FACTOR}}/"

PERF="perf stat -x ';' -dddd -o"
THREADS=({threads_str})
QUERIES=({queries_str})
vectorsizes=({vectorsizes_str})

MAX_THREAD={machine.max_threads}
for compiler in "${{COMPILERS[@]}}"; do
    PARAMS="{machine.name}_${{compiler}}_${{TIMESTAMP}}/"
    RESULTS_DIR="${{RESULTS_BASE}}/${{PARAMS}}"
    mkdir -p "$RESULTS_DIR"
done

REPS={experiment.reps}
mreps={experiment.mreps}

for (( rep=0; rep<$mreps; rep++ )); do
    counter=0
    for thread in "${{THREADS[@]}}"; do
        echo $thread
        let counter++ || true

        for compiler in "${{COMPILERS[@]}}"; do
            
            PARAMS="{machine.name}_${{compiler}}_${{TIMESTAMP}}"
            RESULTS_DIR="$RESULTS_BASE/$PARAMS"
            
            for query in "${{QUERIES[@]}}"; do
                PREFIX=""
                
                for vs in "${{vectorsizes[@]}}"; do
                    # Run V
                    echo -e 'about to run: '"${{PREFIX}}"' '"${{PERF}}"' '"${{RESULTS_DIR}}/r${{rep}}_${{query}}v_t${{thread}}.data"' ./run_tpch_'"${{compiler}}"' -q '"${{query}}"' -p '"${{DATA_DIR}}"' -r '"${{REPS}}"' -t '"${{thread}}"' -e "v" -v '"${{vs}}"' > '"${{RESULTS_DIR}}/r${{rep}}_${{query}}v_t${{thread}}"'".csv"'
                    if ! $PREFIX $PERF "$RESULTS_DIR/r${{rep}}_${{query}}v_t${{thread}}.data" ./run_tpch_$compiler -q $query -p $DATA_DIR -r $REPS -t $thread -e "v" -v $vs > "$RESULTS_DIR/r${{rep}}_${{query}}v_t${{thread}}.csv"; then
                        echo "FAILED: Q${{query}} SF=${{SCALE_FACTOR}} T=${{thread}} V=${{vs}}" >> failures.log
                    fi

                    # Run H
                    if ! $PREFIX $PERF "$RESULTS_DIR/r${{rep}}_${{query}}h_t${{thread}}.data" ./run_tpch_$compiler -q $query -p $DATA_DIR -r $REPS -t $thread -e "h" -v $vs > "$RESULTS_DIR/r${{rep}}_${{query}}h_t${{thread}}.csv"; then
                        echo "FAILED: Q${{query}} SF=${{SCALE_FACTOR}} T=${{thread}} V=${{vs}}" >> failures.log
                    fi
                done
            done
            
            if  (( counter % 20 == 0 )); then
                percentage=$(awk -v num="$counter" -v den="$MAX_THREAD" 'BEGIN {{ printf "%.2f%%\\n", (num/den)*100 }}')
                $TEXTME "$HOSTNAME:$counter complete, $percentage coverage (r${{rep}}/${{mreps}})"
            fi
        done
    done
done

$TEXTME "{experiment.name} COMPLETE for {machine.name}!"
popd
"""

    with open(output_path, 'w') as f:
        f.write(script_content)
    
    print(f"Generated bash script: {output_path}")
    return True

if __name__ == "__main__":
    
    # -------------------------------------------------------------
    #                 🔬 Global Experiment Config 🔬
    # -------------------------------------------------------------
    
    global_config = ExperimentConfig(
        name="Baseline",
        scale_factor="sf100",
        queries=[1, 3, 5, 6, 9, 18],
        vector_sizes=[1024],
        reps=5,
        mreps=1
    )

    # noticed that the extremes of the sweeps take a lot longer than any other tests,
    # enabling this mode turns off those tests
    fast_mode:bool = False
    
    def get_sched(max_threads,min_threads=0):
        sched = [i for i in range_test.bisect_range(max_threads if fast_mode == False else max_threads - 1,
                                                    min_threads if fast_mode == False else min_threads + 1)]
        return sched

    # -------------------------------------------------------------
    #                 🧀 Machine & Cheese Configs 🧀
    # -------------------------------------------------------------

    manchego_gcc = CompilerProfile(
        name="gcc", c_bin="gcc", cxx_bin="g++",
        arch_flags="-fno-tree-vectorize -O3 -march=sapphirerapids -mtune=sapphirerapids -mavx512f -mavx512cd -mavx512bw -mavx512dq -mavx512vl -mavx512vnni -mavx512bf16 -mfpmath=sse -funroll-loops -ffast-math -flto -fomit-frame-pointer -fno-semantic-interposition"
    )
    manchego_clang = CompilerProfile(
        name="clang", c_bin="clang", cxx_bin="clang++",
        arch_flags="-O3 -march=sapphirerapids -mtune=sapphirerapids -mavx512f -mavx512cd -mavx512bw -mavx512dq -mavx512vl -mavx512vnni -mavx512bf16 -mfpmath=sse -ffast-math -funroll-loops -flto=thin -fomit-frame-pointer -fno-semantic-interposition -mllvm -unroll-threshold=250"
    )
    manchego = MachineProfile(
        name="manchego",
        max_threads=32,
        thread_schedule=get_sched(32,1),
        compilers=[manchego_gcc, manchego_clang],
        base_build_dir="$HOME/swole/db-engines/build/new-test"
    )

    burrata_gcc = CompilerProfile(
        name="gcc", c_bin="gcc", cxx_bin="g++",
        arch_flags="-03 -march=native -fno-tree-vectorize"
    )
    burrata_clang = CompilerProfile(
        name="clang", c_bin="clang-18", cxx_bin="clang++-18",
        arch_flags="-03 -mcpu=neoverse-n1 -march=armv8-a+simd+sb -mtune=neoverse-n1"
    )
    burrata = MachineProfile(
        name="burrata",
        max_threads=128,
        thread_schedule=get_sched(128,1),
        compilers=[burrata_gcc, burrata_clang]
    )

    dubliner_gcc = CompilerProfile(
        name="gcc", c_bin="gcc", cxx_bin="g++",
        arch_flags="-O3 -march=cascadelake -mtune=cascadelake -mavx512f -mavx512cd -mavx512bw -mavx512dq -mavx512vl -mavx512vnni -mfpmath=sse -funroll-loops -ffast-math -flto -fomit-frame-pointer -fno-semantic-interposition -fno-tree-vectorize"
    )
    dubliner_clang = CompilerProfile(
        name="clang", c_bin="clang-18", cxx_bin="clang++-18",
        arch_flags="-O3 -march=cascadelake -mtune=cascadelake -mavx512f -mavx512cd -mavx512bw -mavx512dq -mavx512vl -mavx512vnni -mfpmath=sse -ffast-math -funroll-loops -flto=thin -fomit-frame-pointer -fno-semantic-interposition -mllvm -unroll-threshold=250"
    )
    dubliner = MachineProfile(
        name="dubliner",
        max_threads=176,
        thread_schedule=get_sched(176,1),
        compilers=[dubliner_gcc, dubliner_clang]
    )

    parmesan_gcc = CompilerProfile(
        name="gcc", c_bin="gcc", cxx_bin="g++",
        arch_flags="-march=native -fno-tree-vectorize"
    )
    parmesan_clang = CompilerProfile(
        name="clang", c_bin="clang-18", cxx_bin="clang++-18",
        arch_flags="-march=armv9-a+sve2+crypto"
    )
    parmesan = MachineProfile(
        name="burrata",
        max_threads=96,
        thread_schedule=get_sched(96,1),
        compilers=[parmesan_gcc, parmesan_clang]
    )




    print("\t🧀 Cheese Sweep Scripts 🧀")
    # Generating with the shared global config
    generate_benchmark_script(machine=parmesan, experiment=global_config)
    generate_benchmark_script(machine=dubliner, experiment=global_config)
    generate_benchmark_script(machine=manchego, experiment=global_config)
    generate_benchmark_script(machine=burrata, experiment=global_config)
