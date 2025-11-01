#!/bin/bash

# shellcheck disable=SC2034
repo=$1
branch=$2
work_dir=$3
target_file=$4

current_pwd="$(pwd)"

cd "${work_dir}/${repo}" || exit

git show remotes/origin/"${branch}":"${target_file}"

cd "${current_pwd}" || exit
