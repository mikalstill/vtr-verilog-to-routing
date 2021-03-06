#!/usr/bin/env bash

for path in "$@"
do
    blif_files=`find $path -name '*.blif'`
    for blif_file in ${blif_files[@]}
    do
        echo
        echo "File: $blif_file"
        #valgrind --leak-check=full --track-origins=yes ./blifparse_test $blif_file
        ./blifparse_test $blif_file 
        exit_code=$?
        if [ $exit_code -ne 0 ]; then
            echo "Error" >&2 
            exit 1
        fi
    done

done
echo "PASSED TEST" >&2
