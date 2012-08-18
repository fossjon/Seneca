#!/bin/bash
host="$1"
conf="moji-fedora-15-arm"
pass="$2"
su - moji -c "/usr/bin/moji client $host $conf $pass" >>/var/log/moji 2>&1
