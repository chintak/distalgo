#!/bin/bash

set -e

logfile=runs.log
arr=("5 5" "5 25" "5 50" "10 5" "10 50" "100 5")

# run CThread

# make clean >/dev/null
# make >/dev/null
rm -f $logfile

echo "CThread lamutex experiments"
for ((i = 0; i < ${#arr[@]}; i++))
do
    ./lamutex ${arr[$i]} &> $logfile;
    grep '###' $logfile
done

cd ../C
make clean >/dev/null
make >/dev/null
rm -f $logfile

echo "C lamutex experiments"
for ((i = 0; i < ${#arr[@]}; i++))
do
    ./lamport ${arr[$i]} &> $logfile;
    grep '###' $logfile
done

cd ../CThread
