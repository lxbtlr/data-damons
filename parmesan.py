from bash_gen import MachineProfile, CompilerProfile, ExperimentConfig, generate_benchmark_script
import range_test

def get_sched(max_threads,min_threads=0, fast_mode=False):
    sched = [i for i in range_test.bisect_range(max_threads if fast_mode == False else max_threads - 1,
                                                min_threads if fast_mode == False else min_threads + 1)]
    return sched


PARM = MachineProfile(
        name="parmesan",
        max_threads=96,
        thread_schedule=get_sched(96,1),
        base_build_dir="/vol/db-engines/build",
        base_results_dir="/vol/results",
        compilers=[]
    )

def mk_conf(experiment_name="Baseline",fast_mode=False, rounds=1,reps=5 ):

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
        vector_sizes=[1024],
        reps=reps,
        mreps=rounds,
        enable_textme=False # Toggle this variable to True to enable the external script
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


def mk_full_tilt_experiment():

    config, get_sched = mk_conf(experiment_name="full_tilt")

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
    print(mk_sve2_experiment()[0])
    print(mk_crc_experiment()[0])
    print(mk_baseline_experiment()[0])
    print(mk_full_tilt_experiment()[0])
    experiments = [mk_full_tilt_experiment(),mk_baseline_experiment(),
                   mk_crc_experiment(),mk_sve2_experiment()]
    for exp,conf in experiments:
        generate_benchmark_script(machine=exp,experiment=conf)
