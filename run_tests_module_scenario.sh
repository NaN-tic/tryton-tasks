#!/bin/bash

if [ -z "$1" ]; then
    echo "Ús: $0 <module>"
    exit 1
fi

timestamp=$(date +"%Y%m%d_%H%M%S")
log_file="test_$1_$timestamp.log"

test_dir="trytond/trytond/modules/$1/tests/"

if [ ! -d "$test_dir" ]; then
    echo "El directori $test_dir no existeix."
    exit 1
fi

# Cercar tots els fitxers que comencen per "test_" en el directori especificat
for filepath in "$test_dir"test_*; do
    if [[ -f "$filepath" ]]; then  # Comprovar que és un fitxer
        filename=$(basename "$filepath")
        echo "Executant: trytests $1 $filename" | tee -a "$log_file"
        python -m unittest discover -s modules/$1/tests/ -p $filename 2>&1 | tee -a "$log_file"
    fi
done
