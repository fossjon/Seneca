#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright 2010, 2011 Red Hat, Inc.
# License: GPLv2
# Author: Dan Horák <dhorak@redhat.com>
#
# Compare the content of a tag between 2 koji instances
#

import sys
import os
import koji
import time
import string
import rpm 
import shutil
import re
import urllib

inherit = False

# get architecture and tag from command line
if len(sys.argv) > 2:
    SECONDARY_ARCH = sys.argv[1]
    tag = sys.argv[2]
    if len(sys.argv) > 3:
        inherit = True
else:
    print("Compare the content of a tag between 2 koji instances")
    print("Usage: %s <arch> <tag>" % sys.argv[0])
    exit(0)

LOCALKOJIHUB = 'http://%s.koji.fedoraproject.org/kojihub' % (SECONDARY_ARCH)
REMOTEKOJIHUB = 'http://koji.fedoraproject.org/kojihub'

# Should probably set these from a koji config file
SERVERCA = os.path.expanduser('~/.fedora-server-ca.cert')
CLIENTCA = os.path.expanduser('~/.fedora-upload-ca.cert')
CLIENTCERT = os.path.expanduser('~/.fedora.cert')

def _rpmvercmp ((e1, v1, r1), (e2, v2, r2)):
    """find out which build is newer"""
    if e1 == "None":
        e1 = "0"
    if e2 == "None":
        e2 = "0"
    rc = rpm.labelCompare((e1, v1, r1), (e2, v2, r2))
    if rc == 1:
        #first evr wins
        return 1
    elif rc == 0:
        #same evr
        return 0
    else:
        #second evr wins
        return -1

def _countMissing (build, builds=None):
    """find how many builds are missing in local koji"""
    if (builds == None):
        builds = remotekojisession.listTagged(tag, inherit=inherit, package=build['package_name'])
    cnt = 0
    local_evr = (str(build['epoch']), build['version'], build['release'])

#    print "local=%s" % build

    for b in builds:
        if (b['package_name'] != build['package_name']):
            continue
#        print "remote[%d]=%s" % (cnt, b)
        remote_evr = (str(b['epoch']), b['version'], b['release'])
        newestRPM = _rpmvercmp(local_evr, remote_evr)
        if newestRPM == 0 or newestRPM == 1:
            break
        cnt += 1
        #if cnt > 5:
        #    break

    return cnt

localkojisession = koji.ClientSession(LOCALKOJIHUB)
remotekojisession = koji.ClientSession(REMOTEKOJIHUB)

# package indexes
local = 0
remote = 0

cnt = {}
cnt['same'] = 0
cnt['newer'] = 0
cnt['older'] = 0
cnt['local_only'] = 0
cnt['remote_only'] = 0
cnt['total_missing_builds'] = 0

pkgs = {}
pkgs["same"] = []
pkgs["newer"] = []
pkgs["older_missing"] = []
pkgs["local"] = []
pkgs["remote_failed"] = []
pkgs["remote_unbuilt"] = []

local_pkgs = sorted(localkojisession.listTagged(tag, inherit=inherit, latest=True), key = lambda pkg: pkg['package_name'])
remote_pkgs = sorted(remotekojisession.listTagged(tag, inherit=inherit, latest=True), key = lambda pkg: pkg['package_name'])

local_num = len(local_pkgs)
remote_num = len(remote_pkgs)

#all_builds = remotekojisession.listTagged(tag, inherit=True)
all_builds = None

#print "pkgs local=%d remote=%d" % (local_num, remote_num)
#print "local[0]=%s" % (local_pkgs[0])
#exit(0)

while (local < local_num) or (remote < remote_num):
#    print "local=%d remote=%d" % (local, remote)

    if (local < local_num) and (remote < remote_num) and (remote_pkgs[remote]['package_name'] == local_pkgs[local]['package_name']):
        local_evr = (str(local_pkgs[local]['epoch']), local_pkgs[local]['version'], local_pkgs[local]['release'])
        remote_evr = (str(remote_pkgs[remote]['epoch']), remote_pkgs[remote]['version'], remote_pkgs[remote]['release'])

        newestRPM = _rpmvercmp(local_evr, remote_evr)
        if newestRPM == 0:
            #print "same: local and remote: %s " % local_pkgs[local]['nvr']
            pkgs["same"].append("<font class='same'>%s</font>" % (local_pkgs[local]['nvr']))
            cnt['same'] += 1
        if newestRPM == 1:
            #print "newer locally: local: %s remote: %s" % (local_pkgs[local]['nvr'], remote_pkgs[remote]['nvr'])
            pkgs["newer"].append("<font class='newer'>%s / %s</font>" % (local_pkgs[local]['nvr'], remote_pkgs[remote]['nvr']))
            cnt['newer'] += 1
        if newestRPM == -1:
            #missing = 0
            missing = _countMissing(local_pkgs[local], builds=all_builds)

            #if missing > 5:
            #    txt = "more than 5"
            #else:
            #    txt = "%d" % missing

            #print "newer remote: local: %s remote: %s with %s build(s) missing" % (local_pkgs[local]['nvr'], remote_pkgs[remote]['nvr'], txt)
            pkgs["older_missing"].append("<font class='older'>%s / %s [%d]</font>" % (local_pkgs[local]['nvr'], remote_pkgs[remote]['nvr'], missing))
            cnt['total_missing_builds'] += missing
            cnt['older'] += 1

        local += 1
        remote += 1

    elif (remote >= remote_num) or ((local < local_num) and (remote_pkgs[remote]['package_name'] > local_pkgs[local]['package_name'])):
        #print "only locally: %s" % local_pkgs[local]['nvr']
        pkgs["local"].append("<font class='local'>%s</font>" % (local_pkgs[local]['nvr']))
        local += 1
        cnt['local_only'] += 1

    elif (local >= local_num) or ((remote < remote_num) and (remote_pkgs[remote]['package_name'] < local_pkgs[local]['package_name'])):
        #print "only remote: %s" % remote_pkgs[remote]['nvr']
        for x in range(0, 3):
            try:
                params = urllib.urlencode({'match': "glob", 'type': "package", 'terms': remote_pkgs[remote]['package_name']})
                f = urllib.urlopen("http://%s.koji.fedoraproject.org/koji/search?%s" % (SECONDARY_ARCH, params))
                d = f.read()
                break
            except:
                d = ""
                pass
        d = d.replace("\0","").replace("\t","").replace("\r","").replace("\n","")
        d = d.replace("<tr","\n<tr").replace("</tr","</tr\n")
        l = d.split("\n")
        e = ""
        for i in l:
            r = re.match("^<tr.*class.*row.*<a.*href.*(buildinfo.buildID=[0-9]+)[^>]*>([^<]*)</a>.*class.*failed.*$", i)
            if (r):
                e = ("<a href='http://%s.koji.fedoraproject.org/koji/%s' class='failed'>%s</a>" % (SECONDARY_ARCH, r.group(1), r.group(2)))
                break
        if (e == ""):
            pkgs["remote_unbuilt"].append("<font class='unbuilt'>%s</font>" % (remote_pkgs[remote]['nvr']))
        else:
            pkgs["remote_failed"].append(e)
        remote += 1
        cnt['remote_only'] += 1

#print "statistics: %s" % cnt

def ptchart(c0, c1, c2, c3, c4, c5, s):
    return ((c0+" |").rjust(s)+(c1+" |").rjust(s)+(c2+" |").rjust(s)+(c3+" |").rjust(s)+(c4+" |").rjust(s)+(c5+" |").rjust(s))

s = 15

print("%s : %s vs PA" % (tag, SECONDARY_ARCH))
print("")
print(ptchart("Same", "Newer", "Older", "Local", "Remote", "Missing", s))
print("-" * (s * 6))
print(ptchart(str(cnt['same']),str(cnt['newer']),str(cnt['older']),str(cnt['local_only']),str(cnt['remote_only']),str(cnt['total_missing_builds']),s))

sys.stderr.write("""
<html>
	<head>
		<title>Koji Compare Web</title>
		
		<style>
			body
			{
				background-color: #EEEEEE;
				font-family: Courier;
			}
			
			a
			{
				text-decoration: none;
			}
			
			table
			{
				width: 100%%;
			}
			
			td
			{
				border: 1px dotted black;
				background-color: #FFFFFF;
				text-align: right;
				vertical-align: top;
			}
			
			.same
			{
				color: #00CC00;
			}
			
			.newer
			{
				color: #0066CC;
			}
			
			.older
			{
				color: #87421F;
			}
			
			.local
			{
				color: #9900CC;
			}
			
			.unbuilt
			{
				color: #FF6600;
			}
			
			.failed
			{
				color: #CC0000;
			}
			
			.hide
			{
				display: none;
			}
			
			.show
			{
				display: block;
			}
		</style>
		
		<script>
			function swidisp(listname)
			{
				if (document.getElementById(listname).className.match(/^.*hide.*$/))
				{
					document.getElementById(listname).className = "show";
				}
				
				else
				{
					document.getElementById(listname).className = "hide";
				}
			}
		</script>
	</head>
	
	<body>
		<h1>%s-%s</h1>
		
		<table>
			<tr>
				<td><a href="javascript:swidisp('same');"><font class="same">Same<br />[%d]</font></a></td>
				<td><a href="javascript:swidisp('newer');"><font class="newer">Newer<br />[%d]</font></a></td>
				<td><a href="javascript:swidisp('older');"><font class="older">Older / Missing<br />[%d] / [%d]</font></a></td>
				<td><a href="javascript:swidisp('local');"><font class="local">Local Only<br />[%d]</font></a></td>
				<td><a href="javascript:swidisp('unbuilt');"><font class="unbuilt">Remote - Unbuilt<br />[%d]</font></a></td>
				<td><a href="javascript:swidisp('failed');"><font class="failed">Remote - Failed<br />[%d]</font></a></td>
			</tr>
			
			<tr>
				<td><div id="same" class="hide">%s</div></td>
				<td><div id="newer" class="hide">%s</div></td>
				<td><div id="older" class="hide">%s</div></td>
				<td><div id="local" class="hide">%s</div></td>
				<td><div id="unbuilt" class="hide">%s</div></td>
				<td><div id="failed" class="show">%s</div></td>
			</tr>
		</table>
	</body>
</html>
""" % (tag, SECONDARY_ARCH, len(pkgs["same"]), len(pkgs["newer"]), len(pkgs["older_missing"]), cnt['total_missing_builds'], len(pkgs["local"]), len(pkgs["remote_unbuilt"]), len(pkgs["remote_failed"]), "<br />\n".join(pkgs["same"]), "<br />\n".join(pkgs["newer"]), "<br />\n".join(pkgs["older_missing"]), "<br />\n".join(pkgs["local"]), "<br />\n".join(pkgs["remote_unbuilt"]), "<br />\n".join(pkgs["remote_failed"])))
