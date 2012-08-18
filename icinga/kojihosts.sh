#!/bin/bash
x=0
rm -f koji.hosts.txt
while [ $x -lt 5 ]
do
    let p="${x} * 50"
    echo "[${p}]"
    curl -sL "http://arm.koji.fedoraproject.org/koji/hosts?start=${p}&state=all&order=name" > /tmp/koji.hosts.tmp.log
    cat /tmp/koji.hosts.tmp.log | grep -i '<a href="hostinfo.hostID=[0-9][0-9]*">[^<][^<]*</a>' | sed -e 's@^.*<a href="hostinfo.hostID=\([0-9][0-9]*\)">\([^<][^<]*\)</a>.*$@\1 \2@g' >> koji.hosts.txt
    let x="${x} + 1"
done
