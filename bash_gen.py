import os
from dataclasses import dataclass, field
from typing import List

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


@dataclass
class MachineProfile:
    """
    Stores machine-specific configuration for benchmark testing.

    params :

    name - <str> The identifier for the machine (e.g., 'manchego', 'burrata').
    max_threads - <int> The maximum number of hardware threads available.
    thread_schedule - <List[int]> The specific interleaved order of threads to test.
    compilers - <List[CompilerProfile]> A list of available compiler profiles for this machine.
    build_dir - <str> The base directory where CMake should build the binaries.

    returns :

    self - <MachineProfile> The initialized dataclass instance.
    """
    name: str
    max_threads: int
    thread_schedule: List[int]
    compilers: List[CompilerProfile] = field(default_factory=list)
    build_dir: str = "$HOME/swole/db-engines/build/release"


@dataclass
class ExperimentConfig:
    """
    Stores global experiment parameters like reps and data scale.

    params :

    name - <str> The name of the experiment.
    scale_factor - <str> The scale factor directory for the dataset.
    reps - <int> The number of internal benchmark repetitions.
    mreps - <int> The number of macro repetitions (outer loop).
    vectorsizes - <List[int]> The vector sizes to test.
    queries - <List[int]> The TPCH queries to run.

    returns :

    self - <ExperimentConfig> The initialized dataclass instance.
    """
    name: str = "HIGH_RES_SAMPLING"
    scale_factor: str = "sf100"
    reps: int = 5
    mreps: int = 1
    vectorsizes: List[int] = field(default_factory=lambda: [1024])
    queries: List[int] = field(default_factory=lambda: [1, 3, 5, 6, 9, 18])


def generate_benchmark_script(machine: MachineProfile, config: ExperimentConfig, output_path: str = None) -> bool:
    """
    Generates a tailored bash script for compiling and running a benchmark.

    params :

    machine - <MachineProfile> The profile containing architecture-specific configuration.
    config - <ExperimentConfig> The configuration controlling the experiment parameters.
    output_path - <str> Optional. The file path where the script will be saved. 
                        If None, saves as 'run_{machine.name}.sh'.

    returns :

    success - <bool> True if the script was generated successfully.
    """
    
    if output_path is None:
        output_path = f"run_{machine.name}.sh"

    # 1. Format the Compiler bash logic dynamically
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

    # 2. Format the arrays for bash injection
    threads_str = " ".join(map(str, machine.thread_schedule))
    queries_str = " ".join(map(str, config.queries))
    vectorsizes_str = " ".join(map(str, config.vectorsizes))

    # 3. Build the bash script template
    script_content = f"""#!/bin/bash
#SBATCH --job-name={machine.name}_test
#SBATCH --output={machine.name}_test_%j.out
#SBATCH --error={machine.name}_test_%j.err
#SBATCH --exclusive

set -e
cd $HOME
machine="{machine.name}"

EXPERIMENT_NAME="{config.name}"
SCALE_FACTOR="{config.scale_factor}"
TEXTME="/tank/project/text/text-alex"

COMPILERS=({compiler_names})
BASE_BUILD_DIR="{machine.build_dir}"

mkdir -p "$BASE_BUILD_DIR"

echo "========================================"
echo "PHASE 1: BUILD KERNELS"
echo "========================================"

for compiler in "${{COMPILERS[@]}}"; do
    echo "Building for $compiler..."
    {compiler_bash_logic}
     
    COMMON_FLAGS="-O3 -fPIC -Wall -Wextra -Wno-unknown-pragmas"
    BASE_CXX_FLAGS="-std=c++17"
    BASE_C_FLAGS="-fdiagnostics-color"
    
    FINAL_CXX_FLAGS="$COMMON_FLAGS $BASE_CXX_FLAGS $ARCH_FLAGS"
    FINAL_C_FLAGS="$COMMON_FLAGS $BASE_C_FLAGS $ARCH_FLAGS"
    
    # Isolate builds by creating a compiler-specific subdirectory
    COMPILER_BUILD_DIR="$BASE_BUILD_DIR/$compiler"
    mkdir -p "$COMPILER_BUILD_DIR"
    pushd "$COMPILER_BUILD_DIR"
    
    rm -rf CMakeCache.txt CMakeFiles/

    # Note: pointing cmake 3 directories up because we are inside build_dir/compiler/
    cmake ../../.. \\
          -DCMAKE_C_COMPILER="$C_BIN" \\
          -DCMAKE_CXX_COMPILER="$CXX_BIN" \\
          -DCMAKE_CXX_FLAGS="$FINAL_CXX_FLAGS" \\
          -DCMAKE_C_FLAGS="$FINAL_C_FLAGS" \\
          -DCMAKE_BUILD_TYPE=Release || {{ echo "CMAKE failed for $compiler"; $TEXTME "failed in compilation"; exit 1; }}
          
    make run_tpch -j$(nproc) || {{ echo "MAKE failed for $compiler"; $TEXTME "failed in compilation"; exit 1; }}
    
    # Move the executable up to the base build directory
    mv run_tpch "$BASE_BUILD_DIR/run_tpch_$compiler"
    popd
    
    echo "Created run_tpch_$compiler in $BASE_BUILD_DIR"
done

RESULTS_BASE="/tank/project/swole/hi_res/${{SCALE_FACTOR}}"

echo "========================================"
echo "PHASE 2: DIRECT EXECUTION (UNROLLED)"
echo "========================================"

# Move to the base build directory to run the executables
cd "$BASE_BUILD_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATA_DIR="/tank/alexb/swole/tpch/${{SCALE_FACTOR}}/"

PERF="perf stat -x ';' -dddd -o"
THREADS=({threads_str})
QUERIES=({queries_str})
vectorsizes=({vectorsizes_str})

MAX_THREAD={machine.max_threads}
REPS={config.reps}
mreps={config.mreps}

for compiler in "${{COMPILERS[@]}}"; do
    PARAMS="${{HOSTNAME}}_${{compiler}}_${{TIMESTAMP}}/"
    RESULTS_DIR="${{RESULTS_BASE}}/${{PARAMS}}"
    mkdir -p "$RESULTS_DIR"
done

for (( rep=0; rep<$mreps; rep++ )); do
    counter=0
    for thread in "${{THREADS[@]}}"; do
        echo $thread
        let counter++ || true

        for compiler in "${{COMPILERS[@]}}"; do
            PARAMS="${{HOSTNAME}}_${{compiler}}_${{TIMESTAMP}}"
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
            
        done
        if  (( counter % 20 == 0 )); then
            percentage=$(awk -v num="$counter" -v den="$MAX_THREAD" 'BEGIN {{ printf "%.2f%%\\n", (num/den)*100 }}')
            $TEXTME "$HOSTNAME:$counter complete, $percentage coverage (r${{rep}}/${{mreps}})"
        fi
    done
done

$TEXTME "HIGHRES COMPLETE for {machine.name}!"
"""

    with open(output_path, 'w') as f:
        f.write(script_content)
    
    print(f"Generated bash script: {output_path}")
    return True

if __name__ == "__main__":
    import range_test
    # noticed that the extremes of the sweeps take a lot longer than any other tests,
    # enabling this mode turns off those tests
    fast_mode:bool = False
    
    

    def get_sched(max_threads,min_threads=0):
        sched = [i for i in range_test.bisect_range(max_threads if fast_mode == False else max_threads - 1,
                                                    min_threads if fast_mode == False else min_threads + 1)]
        return sched

#############################################################
#
#                 🧀 Cheese Configs 🧀
#
#############################################################
    baseline_conf = ExperimentConfig(
        name="Baseline",
        scale_factor="sf100",
        reps=5,
        mreps=1,
        vectorsizes=[1024], 
        queries=[1, 3, 5, 6, 9, 18])

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
        #build_dir="$HOME/swole/db-engines/build/new-test"
    )

    burrata_gcc = CompilerProfile(
        name="gcc", c_bin="gcc", cxx_bin="g++",
        arch_flags="-march=native -fno-tree-vectorize"
    )
    burrata_clang = CompilerProfile(
        name="clang", c_bin="clang-18", cxx_bin="clang++-18",
        arch_flags="-mcpu=neoverse-n1 -march=armv8-a+simd+sb -mtune=neoverse-n1"
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


    print("\t🧀 Cheese Sweep Scripts 🧀")
    generate_benchmark_script(machine=dubliner, config=baseline_conf)
    generate_benchmark_script(machine=manchego, config=baseline_conf)
    generate_benchmark_script(machine=burrata,  config=baseline_conf)
