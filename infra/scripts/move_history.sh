#!/bin/bash -e

# move_history.sh
# 9/2017
# Andrew Reynolds
#
# Moves the history from git source to target repo
export source=$1
export target=$2

rm /tmp/patch/*
git format-patch -o /tmp/patch $(git log $source|grep ^commit|tail -1|awk '{print $2}')^..HEAD $source
cd $target
git am /tmp/patch/*.patch

