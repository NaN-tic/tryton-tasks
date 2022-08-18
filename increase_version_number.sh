for dir in modules/*
do
    dir=${dir%*/}

    if [ ! -d "$dir" ]; then
      continue
    fi

    echo ${dir##*/}
    cd $PWD'/'${dir}
    git checkout -b 6.4
    sed -i 's/version=\(.*\)/version=6.4.0/' tryton.cfg
    git commit -a -m "Branch 6.4"
    git push -u origin 6.4
    git checkout main
    sed -i 's/version=\(.*\)/version=6.5.0/' tryton.cfg
    git commit -a -m "Increase version number"
    git push --all
    cd "$OLDPWD"
done
