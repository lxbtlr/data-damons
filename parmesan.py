from bash_gen import MachineProfile, CompilerProfile, ExperimentConfig, generate_benchmark_script
import range_test

def get_sched(max_threads,min_threads=0, fast_mode=False):
    sched = [i for i in range_test.bisect_range(max_threads if fast_mode == False else max_threads - 1,
                                                min_threads if fast_mode == False else min_threads + 1)]
    return sched

COVERAGE:float = .4
sched = get_sched(96,1)
sched = sched[:int(len(sched)*COVERAGE)]
PARM = MachineProfile(
        name="parmesan",
        max_threads=96,
        thread_schedule=sched,
        base_build_dir="/vol/db-engines/build",
        base_results_dir="/vol/results",
        compilers=[]
    )

def mk_conf(experiment_name="Baseline",fast_mode=False, rounds=1,reps=5 , vector_sizes=[1024],prefix=""):

    # -------------------------------------------------------------
    #                 🔬 Global Experiment Config 🔬
    # -------------------------------------------------------------
    
    assert type(experiment_name) == str
    assert type(fast_mode) == bool
    
    assert type(rounds) == int
    assert type(reps) == int
    
    conf = ExperimentConfig(
        name=experiment_name,
        scale_factor="sf100",
        queries=[1, 3, 5, 6, 9, 18],
        vector_sizes=vector_sizes[:int(len(vector_sizes)*COVERAGE)],
        reps=reps,
        mreps=rounds,
        enable_textme=False, # Toggle this variable to True to enable the external script
        pre_script_cmd= prefix
    )

    # noticed that the extremes of the sweeps take a lot longer than any other tests,
    # enabling this mode turns off those tests
    
    def get_sched(max_threads,min_threads=0):
        sched = [i for i in range_test.bisect_range(max_threads if fast_mode == False else max_threads - 1,
                                                    min_threads if fast_mode == False else min_threads + 1)]
        return sched
    
    return conf, get_sched

def mk_baseline_experiment():

    config, get_sched = mk_conf()
    
    parmesan_gcc = CompilerProfile(
        name="gcc", c_bin="gcc", cxx_bin="g++",
        arch_flags="-O3 -march=native -fno-tree-vectorize"
    )
    parmesan_clang = CompilerProfile(
        name="clang", c_bin="clang-18", cxx_bin="clang++-18",
        arch_flags="-march=armv9-a"
    )
    expr = PARM
    expr.compilers = [parmesan_clang,parmesan_gcc]
    return expr,config

def mk_crc_experiment():

    config, get_sched = mk_conf(experiment_name="crc")

    parmesan_gcc = CompilerProfile(
        name="gcc", c_bin="gcc", cxx_bin="g++",
        arch_flags="-O3 -march=native -fno-tree-vectorize"
    )
    parmesan_clang = CompilerProfile(
        name="clang", c_bin="clang-18", cxx_bin="clang++-18",
        arch_flags="-march=armv9-a+crypto"
    )
    expr = PARM
    expr.compilers = [parmesan_clang,parmesan_gcc]
    
    return expr,config


def mk_sve2_experiment():

    config, get_sched = mk_conf(experiment_name="sve2")

    parmesan_gcc = CompilerProfile(
        name="gcc", c_bin="gcc", cxx_bin="g++",
        arch_flags="-march=native -fno-tree-vectorize"
    )
    parmesan_clang = CompilerProfile(
        name="clang", c_bin="clang-18", cxx_bin="clang++-18",
        arch_flags="-march=armv9-a+sve2"
    )
    expr = PARM
    expr.compilers = [parmesan_clang,parmesan_gcc]
    
    return expr,config


def mk_full_tilt_experiment(suffix=""):

    if suffix != "":
        config, get_sched = mk_conf(experiment_name=f"full_tilt_{suffix}",prefix=f"source /vol/scripts/{suffix}.sh")
    else:
        config, get_sched = mk_conf(experiment_name=f"full_tilt")

    parmesan_gcc = CompilerProfile(
        name="gcc", c_bin="gcc", cxx_bin="g++",
        arch_flags="-O3 -march=native -fno-tree-vectorize"
    )
    parmesan_clang = CompilerProfile(
        name="clang", c_bin="clang-18", cxx_bin="clang++-18",
        arch_flags="-march=armv9-a+sve2+crypto"
    )
    expr = PARM
    expr.compilers = [parmesan_clang,parmesan_gcc]
    
    return expr,config

import math
def mk_vs_experiment(suffix="", vs_range=[1,1024], coverage:float=1):

    vectorsizes = [i**2 for i in range_test.bisect_range(int(vs_range[1]**(1/2) +1), 
                 int(vs_range[0]**(1/2)))]
    
    if suffix != "":
        config, get_sched = mk_conf(experiment_name=f"vs_{suffix}",prefix=f"source /vol/scripts/{suffix}.sh", vector_sizes=vectorsizes[:int(len(vectorsizes)*COVERAGE)])
    else:
        config, get_sched = mk_conf(experiment_name=f"vs", vector_sizes=vectorsizes[:int(len(vectorsizes)*COVERAGE)])

    parmesan_gcc = CompilerProfile(
        name="gcc", c_bin="gcc", cxx_bin="g++",
        arch_flags="-O3 -march=native -fno-tree-vectorize"
    )
    parmesan_clang = CompilerProfile(
        name="clang", c_bin="clang-18", cxx_bin="clang++-18",
        arch_flags="-march=armv9-a+sve2"
    )
    expr = PARM
    expr.compilers = [parmesan_clang,parmesan_gcc]
    
    return expr,config


if __name__ == "__main__":

    print("Generating Experiment Scripts for:")
    # print(mk_sve2_experiment()[0])
    # print(mk_crc_experiment()[0])
    # print(mk_baseline_experiment()[0])
    # print(mk_full_tilt_experiment()[0])

    experiments = [#mk_full_tilt_experiment(suffix="exp1"),
                   #mk_full_tilt_experiment(suffix="exp2"),
                   #mk_full_tilt_experiment(suffix="exp3"),
                   #mk_full_tilt_experiment(suffix="exp4"),
                   #mk_full_tilt_experiment(suffix="exp5"),
                   mk_full_tilt_experiment(suffix="exp6"),
                   mk_vs_experiment(suffix="exp1",vs_range=[1,4194304]),
                   mk_vs_experiment(suffix="exp2",vs_range=[1,4194304]),
                   mk_vs_experiment(suffix="exp3",vs_range=[1,4194304]),
                   mk_vs_experiment(suffix="exp4",vs_range=[1,4194304]),
                   mk_vs_experiment(suffix="exp5",vs_range=[1,4194304]),
                   mk_vs_experiment(suffix="exp6",vs_range=[1,4194304]),
                   ]
    #[mk_full_tilt_experiment(),mk_baseline_experiment(), mk_crc_experiment(),mk_sve2_experiment()]
    for exp,conf in experiments:
        generate_benchmark_script(machine=exp,experiment=conf)
