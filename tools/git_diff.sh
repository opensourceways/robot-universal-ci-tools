#!/bin/bash

# shellcheck disable=SC2034
repo=$1
branch=$2
work_dir=$3
args=$4
target_file=$5

current_pwd="$(pwd)"

cd "${work_dir}/${repo}" || exit

cmd="git diff "
if [ "${args}" ]; then
  cmd+="${args}"
fi

cmd+=" remotes/origin/${branch} "

if [ "${target_file}" ]; then
  cmd+="${target_file}"
fi

$cmd

cd "${current_pwd}" || exit
