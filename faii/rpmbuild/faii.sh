#!/bin/bash

pd="$1"
vs='1.0.0'

if [ "$1" == "" ]
then
	echo "need directory to faii folder"
	exit 1
fi

rpmdev-wipetree ; rm -rf ~/rpmbuild/BUILDROOT/*

echo ; tree ~/rpmbuild ; echo

rm -rf /tmp/fedora-arm-installer-$vs 2> /dev/null
cp -rf $pd/source /tmp/fedora-arm-installer-$vs
tar -czvf $pd/rpmbuild/faii-$vs.tar.gz --exclude=*.exe -C /tmp fedora-arm-installer-$vs
cp $pd/rpmbuild/fedora-arm-installer.spec ~/rpmbuild/SPECS/
cp $pd/rpmbuild/faii-$vs.tar.gz ~/rpmbuild/SOURCES/

echo ; tree ~/rpmbuild ; echo

echo "rpmbuild -ba ~/rpmbuild/SPECS/fedora-arm-installer.spec"
echo "cp -v ~/rpmbuild/SRPMS/* $pd/rpmbuild/"
echo "cp -v ~/rpmbuild/RPMS/noarch/* $pd/binary/"
echo "scp $pd/rpmbuild/* fossjon@fedorapeople.org:~/public_html/"
