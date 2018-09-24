#!/usr/bin/env python3

import os
import sys
import subprocess
import time


timeout = 3*60*60*2
memory_limit = 15*1024*1024
timeout_command = "timeout_perl -t {} -m {} "
miningzinc_list_command = "miningzinc list {} {}"
miningzinc_solve_command = "miningzinc solve -p {} {} {} --show_solutions"
mkdir_command = "mkdir -p {}"
# extra_param = "\"Cost={}; costs={}; MinFreq={};\""
def main():
    mode = sys.argv[1]
    model = sys.argv[2]
    init_param = sys.argv[3]
    freq = int(sys.argv[4])
    path = sys.argv[5]
    key_flag = False
    if path.startswith("-keywords="):
        keywords = path.split("=")[1].split(",")
        key_flag = True
    costs, utils , min_cost, max_cost, occur = get_freq_and_costs_from_essence(init_param, freq, mode)
    new_param = create_new_param(init_param, max_cost, costs, utils ,min_cost, freq, occur)
    mzinc_command = miningzinc_list_command.format(model, new_param)
    print(mzinc_command)
    mzinc_process = subprocess.Popen(mzinc_command.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in iter(mzinc_process.stdout.readline, b''):
        print(line.decode()[:-1])
        if key_flag:
            count=0
            for keyword in keywords:
                if keyword.startswith("-"):
                    if keyword[1:] not in line.decode():
                        count+=1
                else:
                    if keyword in line.decode():
                        count+=1
            if count==len(keywords):
                path=line.decode().strip().split(":")[0]
                break
    mzinc_command = miningzinc_solve_command.format(path, model, new_param)
    new_timeout_command = timeout_command.format(timeout, memory_limit)
    mzinc_command = new_timeout_command + mzinc_command
    print(mzinc_command)
    info_files_dir = "info-files/"
    mkdir_process = subprocess.Popen(mkdir_command.format(info_files_dir).split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in iter(mkdir_process.stdout.readline, b''):
        print(line.decode()[:-1])
    info_file = info_files_dir+init_param.split(".")[0].split("/")[-1]+"_f_"+str(freq)+"_mz_info.txt"
    mzinc_process = subprocess.Popen(mzinc_command.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in iter(mzinc_process.stdout.readline, b''):
        if "{" not in line.decode() and "--------" not in line.decode():
            print(line.decode()[:-1])
            if "RESULT" in line.decode():
                sol_size = int(line.decode().split(":")[1].split(",")[0].strip())
                # print("sooool"+sol_size)
                with open(info_file, "w") as f:
                    f.write("1st interpretation sol size: {} \n".format(sol_size))
        if "list index out of range" in line.decode():
            sys.exit(66)
        elif "returned non-zero exit status 1" in line.decode():
            sys.exit(55)

def get_freq_and_costs_from_essence(init_param, freq, mode):
    essence_param = init_param.split("-m")[0]+"_"+str(freq)+".param"
    with open (essence_param, "r") as f:
        lines = f.readlines()
    count = 0
    costs = None
    max_cost = None
    for line in lines:
        if mode != "closed_only" and "$" not in line:
            if "min_utility" in line :
                min_util = line[:-1].split("be ")[1]
            elif "max_cost" in line :
                max_cost = line[:-1].split("be ")[1]
            elif "utility_values" in line:
                utils = line[:-1].split("be ")[1].split(";")[0]+"]"
            elif "cost_values" in line:
                costs = line[:-1].split("be ")[1].split(";")[0]+"]"
        if line.startswith("{"):
            count += 1
    occur = round((count)*freq/100)
    return costs, utils, min_util, max_cost, occur

def create_new_param(init_param, max_cost, costs, utils, min_util, freq, occur):
    new_param = init_param.split(".")[0]+"_"+str(freq)+".dat"
    with open(init_param, "r") as f:
        lines = f.readlines()
    with open(new_param, "w") as f:
        f.writelines(lines)
        if max_cost is not None:
            f.write("\nCost="+str(max_cost)+";\n")
        if costs is not None:
                f.write("costs="+str(costs)+";\n")
        if utils is not None:
                f.write("utils="+str(utils)+";\n")
        if min_util is not None:
                f.write("Util="+str(min_util)+";\n")
        f.write("MinFreq="+str(occur)+";\n")
    return new_param
if __name__ == '__main__':
    main()