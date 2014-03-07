#!/bin/bash

if [ -f "/usr/local/bin/virtualenvwrapper.sh" ]; then
    script=/usr/local/bin/virtualenvwrapper.sh
elif [ -f "/usr/share/virtualenvwrapper/virtualenvwrapper.sh" ]; then
    script=/usr/share/virtualenvwrapper/virtualenvwrapper.sh
fi
source $script
workon tryton
echo $VIRTUAL_ENV

$*
