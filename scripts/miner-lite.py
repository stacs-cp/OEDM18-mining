#!/usr/bin/env python3

import os
import sys
import subprocess
import time
import json
# import exploder

VERSION = "0.6"

eclat_timeout = 180
eclat_memory_limit = 15*1024*1024
freq_str ="letting min_freq be {}\n"
eclat_size_command = "eclat -tm -s{} -Z {}"
timeout_command = "timeout_perl -t {} -m {} "
conjure_trans_param_command = "conjure translate-param --eprime={} --essence-param={} --eprime-param={} --line-width=2500"
savilerow_command = "savilerow {} {} -sat -sat-family nbc_minisat_all -run-solver -solutions-to-stdout-one-line -preproc-time-limit 0"
# -minion-bin minion -preprocess SACBounds_limit"
mkdir_command = "mkdir -p {}"
essence_suffix = ".param"
eprime_suffix = ".eprime-param"
def main():
    if len(sys.argv) < 5:
        print_help_text()
        sys.exit()
    mode = sys.argv[1]
    model = sys.argv[2]
    init_param = sys.argv[3]
    freq = int(sys.argv[4])
    solve(mode, model, init_param, freq)

def solve(mode, model, init_param, freq):    
    start_time  = time.time()
    if "c" not in mode and "m" not in mode:
        print_help_text()
        sys.exit()
    start_size, eclat_time = get_start_size_from_eclat(freq, init_param)
    if start_size == 0:
        sys.exit(0)
    elif start_size == -1:
        start_size = get_max_row_card(init_param)
    stats = dict()
    stats["Eclat time"] = eclat_time
    conjure_output_dir = "output/{}/".format(model.split(".")[0])
    mkdir_process = subprocess.Popen(mkdir_command.format(conjure_output_dir).split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in iter(mkdir_process.stdout.readline, b''):
        print(line.decode()[:-1])
    new_essence_param = gen_new_essence_param(init_param, essence_suffix, freq, mode)
    init_eprime_param = conjure_output_dir+new_essence_param.split(".")[0].split("/")[-1]+eprime_suffix
    #this is different
    info_files_dir = "info-files/"
    mkdir_process = subprocess.Popen(mkdir_command.format(info_files_dir).split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in iter(mkdir_process.stdout.readline, b''):
        print(line.decode()[:-1])
    info_file =info_files_dir+new_essence_param.split(".")[0].split("/")[-1]+"_em_info.txt"
    new_conjure_command = conjure_trans_param_command.format(model, new_essence_param, init_eprime_param)
    print(new_conjure_command)
    conjure_start_time = time.time()
    conjure_process = subprocess.Popen(new_conjure_command.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in iter(conjure_process.stdout.readline, b''):
        print(line.decode()[:-1])
    conjure_end_time = time.time()
    ## edit eprime file
    edit_eprime_file(init_eprime_param, start_size)
    stats["Conjure translate param time"] = conjure_end_time - conjure_start_time
    stats["SolverTotalTime Sum"] = 0
    stats["SavileRowTime Sum"] = 0
    stats["SavileRow Command time"] = 0
    stats["Number of solutions"] = 0
    sr_start_time = time.time()
    new_savilerow_command = savilerow_command.format(model, init_eprime_param)
    print(new_savilerow_command)
    savilerow_process = subprocess.Popen(new_savilerow_command.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    solutions = []
    for line in iter(savilerow_process.stdout.readline, b''):
        code, result, result_occ = get_solution(line.decode(), mode)
        if code == True:
            add_solution(result, result_occ, solutions, mode)
        else:
            if line.decode().startswith("Looking"):
                print("Solutions so far: {}".format(len(solutions)))
            print(line.decode()[:-1])
    sr_end_time = time.time()
    stats["SavileRow Command time"] += sr_end_time-sr_start_time
    stats = get_savilerow_stats(init_eprime_param, stats)
    nc_time_st = time.time()
    # nc_solutions_size = len(exploder.explode_solutions(solutions, init_param))
    stats["Number of solutions"] = len(solutions)
    stats["Number of frequent solutions"] = -1 # nc_solutions_size
    nc_time_end = time.time()
    stats["Exploding frequent solutions time"] = nc_time_end - nc_time_st
    end_time = time.time()
    stats["Script Total time"] = end_time-start_time
    print_and_store_results(freq, mode, stats, info_file, solutions)
    return solutions

def edit_eprime_file(init_eprime_param, start_size):
    with open(init_eprime_param, "r") as f:
        lines = f.readlines()

    with open(init_eprime_param, "w") as f:
        f.writelines(lines)
        buff = "letting sizes be [ "
        for i in range(start_size, -1, -1):
            buff += str(i) + ", "
        f.write(buff[:-2]+" ]")


def add_solution(result, result_occ, solutions, mode):
    sol = {"Set (Occurrence)": result}
    if result_occ is not None:
        sol["Count"] = result_occ
    occurrence_sol_to_explicit_sol(sol)
    solutions.append(sol)

def get_solution(line, mode):
    if line.startswith("Solution"):
        if mode == "c":
            solution = line.strip().split("freq_items_1_Occurrence be ")[1].split(';int(')[0] + "]"
            if "freq_items_2" in line:
                solution_occ = line.strip().split(" freq_items_2 be ")[1]
            else:
                solution_occ = None
        elif mode == "m":
            solution = line.strip().split("freq_items_Occurrence be ")[1].split(';int(')[0] + "]"
            solution_occ = None
        return True, solution, solution_occ
    else:
        return False, False, False

def occurrence_sol_to_explicit_sol(solution):
    explicit_sol = []
    split_sol = solution["Set (Occurrence)"][1:-1].split(", ")
    for i in range(len(split_sol)):
        if split_sol[i] == "true":
            explicit_sol.append(i)
    solution["Set"] = explicit_sol
    solution.pop("Set (Occurrence)")

def get_savilerow_stats(eprime_param, stats):
    with open(eprime_param+".info", "r") as f:
        lines = f.readlines()
    for line in lines:
        if "SolverTotalTime" in line:
            solver_time = line.split(":")[1].split("\n")[0]
            stats["SolverTotalTime Sum"] += float(solver_time)
        elif "SavileRowTotalTime" in line:
            solver_time = line.split(":")[1].split("\n")[0]
            stats["SavileRowTime Sum"] += float(solver_time)
    return stats

def print_and_store_results(freq, mode, stats, info_file, solutions):
    info_txt = "Freq: "+str(freq)+"% Mode: "+mode+"\n"
    info_txt += "Script Total Time: "+str(stats["Script Total time"])+"\n"
    info_txt += "Eclat time: "+str(stats["Eclat time"])+"\n"
    info_txt += "Conjure translate param time: "+str(stats["Conjure translate param time"])+"\n"
    info_txt += "SavileRow Command time: "+str(stats["SavileRow Command time"])+"\n"
    info_txt += "SavileRowTime Sum: "+str(stats["SavileRowTime Sum"])+"\n"
    info_txt += "SolverTotalTime Sum: "+str(stats["SolverTotalTime Sum"])+"\n"
    info_txt += "Exploding frequent solutions time: "+str(stats["Exploding frequent solutions time"])+"\n"
    info_txt += "Number of solutions: "+str(stats["Number of solutions"])+"\n"
    info_txt += "Number of frequent solutions: "+str(stats["Number of frequent solutions"])+"\n"
    print(info_txt)
    with open(info_file, "w") as f:
        f.write(info_txt)
    print("Info stored in "+info_file)
    sols_json = info_file.split(".")[0]+".json"
    with open(sols_json, "w") as f:
        json.dump(solutions, f, indent=1)
    print("Solutions stored in "+sols_json)    

def gen_new_essence_param(init_param, suffix, freq, mode):
    freq_text = "f_" + str(freq)
    new_param = "{}_{}{}".format(init_param.split(".")[0], freq_text, suffix)
    with open(init_param, "r") as f:
        lines = f.readlines()
    db_starts = []
    db_ends = []
    for i in range(len(lines)):
        line = lines[i]
        if "be mset(" in line:
            db_starts.append(i+1)
        if ")" in line:
            db_ends.append(i-1)
    freq_count = []
    for i in range(len(db_starts)):
        #this would give diff results in python2-3 and also freq diff
        # nb = math.ceil((db_ends[i] - db_starts[i] + 1)*freq/100)
        nb = round((db_ends[i] - db_starts[i] + 1)*freq/100)
        freq_count.append(nb)
    with open(new_param, "w") as f:
        f.writelines(lines)
        f.write(freq_str.format(freq_count[0]))
        for i in range(1, len(db_starts)):
            f.write(freq_str.replace("freq", "freq_"+str(i+1)).format(freq_count[i]))
    return new_param


def get_start_size_from_eclat(freq, init_param):
    nb = get_entry_size(init_param)
    occ = round(nb*freq/100)
    index = init_param.rfind("/")
    raw_param = init_param[:index]+init_param[index:].split(".")[0].split("_")[0]+".dat"
    new_eclat_size_command = eclat_size_command.format("-"+str(occ), raw_param)        
    new_timeout_command = timeout_command.format(eclat_timeout, eclat_memory_limit)
    new_eclat_size_command = new_timeout_command + new_eclat_size_command
    print(new_eclat_size_command)
    eclat_start_time = time.time()
    eclat_process = subprocess.Popen(new_eclat_size_command.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print("waiting for eclat to finish")
    size = None
    for line in iter(eclat_process.stdout.readline, b''):
        if "MEM CPU" in line.decode():
            eclat_end_time = time.time()
            eclat_time = eclat_end_time-eclat_start_time
            print("eclat got OOM in {}".format(eclat_time))
            size = -1
        elif "TIMEOUT CPU" in line.decode():
            eclat_end_time = time.time()
            eclat_time = eclat_end_time-eclat_start_time
            print("Eclat got timeout in {}".format(eclat_time))
            size = -1
        elif "FINISHED" in line.decode():
            eclat_end_time = time.time()
            eclat_time = eclat_end_time-eclat_start_time
            print("eclat finished in {}".format(eclat_time))
            break
        else:
            result_line = line
    if "no (frequent) items found" in result_line.decode():
        size = 0
        print("No fis found by eclat in {} s, terminating directly".format(eclat_time))
    if size is None:
        size = int(result_line.decode().split(":")[0].strip())
        print("Maximum cardinality is found as {}".format(size))
    return size, eclat_time

def get_entry_size(init_param):
    index = init_param.rfind("/")
    raw_param = init_param[:index]+init_param[index:].split(".")[0].split("_")[0]+".dat"
    with open(raw_param, "r") as f:
        lines = f.readlines()
        nb = len(lines)
    return nb

def get_max_row_card(param):
    with open(param, "r") as f:
        lines = f.readlines()
    max = 0
    for line in lines:
        count = len(line.split(","))
        if max < count:
            max = count
    return max

def get_item_count(init_param):
    index = init_param.rfind("/")
    raw_param = init_param[:index]+init_param[index:].split(".")[0].split("_")[0]+".dat"
    with open(raw_param, "r") as f:
        lines = f.readlines()
    max_item = -1
    for line in lines:
        for i in line.split():
            if int(i) > max_item:
                max_item = int(i)
    return max_item

def print_help_text():
    print("Usage: python miner.py (m|c) eprime_model essence_init_param freq")
    print("m: maximal fis mining")
    print("c: closed fis mining")

if __name__ == '__main__':
    main()
