LOG_FILE="output.log"

function log_command_output {
    "$@" >> "$LOG_FILE" 2>&1
}

for dir in trytond/trytond/modules/*; do
    dir=${dir%*/}

    if [ ! -d "$dir" ]; then
      continue
    fi

    echo ${dir##*/}
    log_command_output python -m unittest discover -s modules/${dir##*/}/tests/
done
