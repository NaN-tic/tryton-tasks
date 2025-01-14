#!/bin/bash

# Comprova que s'ha proporcionat un directori
if [ -z "$1" ]; then
  echo "Ús: $0 /ruta/al/directori 7.3.0"
  exit 1
fi

# Busca recursivament fitxers tryton.cfg
find "$1" -type f -name "tryton.cfg" | while read -r cfg_file; do
  # Cerca la línia amb version=
  while IFS= read -r line || [[ -n $line ]]; do
    if [[ $line == version=* ]]; then
      version=$(echo "$line" | cut -d'=' -f2)
      if [[ "$version" != $2 ]]; then
        echo "$cfg_file:$(grep -n "$line" "$cfg_file" | cut -d: -f1):$line"
      fi
    fi
  done < "$cfg_file"
done
