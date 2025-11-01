#!/bin/bash

# shellcheck disable=SC2034
repo=$1
branch=$2   # 待切换分支
work_dir=$3

current_pwd="$(pwd)"

cd "${work_dir}/${repo}" || exit

git checkout -b "${branch}"

cd "${current_pwd}" || exit
