#!/bin/bash
if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ]; then
    echo "$0 task(without #) ./path branch"
    exit 0
fi

invoke project.upload_review --work "#$1" --path $2 --branch $3
