#!/bin/bash

# shellcheck disable=SC2034
owner=$1
repo=$2
pr_id=$3
branch=$4
work_dir=$5

current_pwd="$(pwd)"
repo_url="https://gitcode.com/${owner}/${repo}.git"

# init work dir
if [ ! -d "${work_dir}" ]; then
    mkdir -p "${work_dir}"
fi

cd "${work_dir}" || exit

# clear env
if [ -d "${repo}" ]; then
    rm -rf "${repo}"
fi

# clone repo
git clone --depth 100 "${repo_url}"
cd "${repo}" || exit
git checkout "${branch}"
git pull

# fetch pr
git fetch origin refs/merge-requests/"${pr_id}"/head:pr_"${pr_id}"

# create tmp work branch
# define branch name starts with "tmp_pr_"
git checkout -b tmp_pr_"${pr_id}"

# merge pr code to tmp work branch
git merge --no-edit --allow-unrelated-histories "pr_${pr_id}"

cd "${current_pwd}" || exit
