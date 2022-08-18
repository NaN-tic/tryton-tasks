for dir in *
do
    dir=${dir%*/}

    if [ ! -d "$dir" ]; then
      continue
    fi

    echo ${dir##*/}
    cd $PWD'/'${dir}
    git checkout -b 6.4
    sed -i 's/branch = main/branch = 6.4/' local.cfg
    git commit -a -m "Branch 6.4"
    git push -u origin 6.4
    cd "$OLDPWD"
done
