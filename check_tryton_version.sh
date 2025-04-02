#!/bin/bash

if [ -z "$1" ]; then
    echo "Ús: $0 <7.4>"
    exit 1
fi

# Prefix de versió esperat
EXPECTED_PREFIX="$1"

# Cerca recursiva de fitxers tryton.cfg
tmpfile=$(mktemp)
find . -type f -name "tryton.cfg" > "$tmpfile"

while IFS= read -r file; do
    # Extreu la versió del fitxer
    version=$(grep -E '^version=' "$file" | cut -d'=' -f2)

    # Obté només els dos primers segments de la versió (majors i menors)
    version_prefix=$(echo "$version" | cut -d'.' -f1,2)

    # Comprova si la versió és diferent de l'esperada
    if [[ "$version_prefix" != "$EXPECTED_PREFIX" ]]; then
        echo "Directori: $(dirname "$file") -> Versió trobada: $version"
    fi
done < "$tmpfile"

rm "$tmpfile"
