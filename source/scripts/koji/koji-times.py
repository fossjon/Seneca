#!/usr/bin/python
# Based on the work from DJ Delorie (dj@redhat.com)

import ast
import koji
import os
import random
import re
import string
import sys
import time

tag = 'f19'

def ts2hms(ts):
    d = ts / (24*3600)
    h = (ts / 3600) % 24
    m = (ts/60) % 60
    s = ts % 60
    if d >= 1:
        return '%d+%02d:%02d:%02d' % (d, h, m, s)
    else:
        return '%2d:%02d:%02d' % (h, m, s)

hostname = {}
def lookup_host(session, id):
    if not id in hostname:
        host = session.getHost(id)
        hostname[id] = host['name']
    return hostname[id]

def scan_koji(hostr):
    kojis = ['http://koji.fedoraproject.org/kojihub', 'http://arm.koji.fedoraproject.org/kojihub']

    for url in kojis:
        if (os.fork() == 0):
            session = koji.ClientSession(url)
            builds = session.getLatestBuilds(tag=tag)

            subt = 24
            indl = len(builds)
            subl = ((indl / subt) + subt)

            for subi in range(0, subt):
                indx = (subi * subl)
                endi = (indx + subl)

                if (os.fork() == 0):
                    random.seed(os.urandom(subt))
                    rands = ''.join(random.choice(string.digits + string.ascii_uppercase + string.ascii_lowercase) for x in range(subt))
                    fileo = open("/var/tmp/times.%s.%d.csv" % (rands, subi), "w")

                    while ((indx < endi) and (indx < indl)):
                        build = builds[indx]

                        if (not build['task_id'] is None):
                            session = koji.ClientSession(url)
                            ptask = session.getTaskInfo(build['task_id'])
                            ctasks = session.getTaskChildren(build['task_id'])

                            for ctask in ctasks:
                                if ((ctask['method'] == 'buildArch') and ('completion_ts' in ctask) and (not ctask['completion_ts'] is None) and (not ctask['start_ts'] is None)):
                                    host = lookup_host(session, ctask['host_id'])
                                    elapsed = (ctask['completion_ts'] - ctask['start_ts'])
                                    if (re.match("^%s$" % (hostr), host, re.I)):
                                        fileo.write("{'name':'%s','arch':'%s','parent':%s,'id':%s,'time':%s,'elapsed':'%s','info':'%s-%s-%s-%s'}\n" % (build['name'], ctask['arch'], ctask['parent'], ctask['id'], elapsed, ts2hms(elapsed), url, subi, indx, endi))

                            sys.stdout.flush()
                            sys.stderr.flush()

                        indx += 1

                    sys.exit(0)

            sys.exit(0)

if (len(sys.argv) >= 3):
    if (sys.argv[1] == "time"):
        os.system("rm -fv /var/tmp/times.*.csv")
        scan_koji(sys.argv[2])

    if (sys.argv[1] == "html"):
        os.system("cat /var/tmp/times.*.csv | sort | uniq > /var/tmp/times.all.csv")
        filei = open("/var/tmp/times.all.csv", "r")
        times = {}
        for line in filei.readlines():
            ctask = ast.literal_eval(line)
            if (not ctask["name"] in times.keys()):
                times[ctask["name"]] = {}
            times[ctask["name"]][ctask["arch"]] = ctask
        sortd = []
        for keyn in times.keys():
            if (("i386" in times[keyn].keys()) and ("x86_64" in times[keyn].keys()) and ("armhfp" in times[keyn].keys())):
                flag = 0
                diff = (times[keyn]["armhfp"]["time"] - times[keyn]["i386"]["time"])
                for x in range(0, len(sortd)):
                    if (diff > sortd[x][0]):
                        sortd.insert(x, [diff, keyn])
                        flag = 1
                        break
                if (flag == 0):
                    sortd.append([diff, keyn])
        print("""
            <html>
                <head>
                    <style>
                        body
                        {
                            font-family: monospace;
                        }

                        a
                        {
                            color: #0066CC;
                            text-decoration: none;
                        }
                    </style>
                </head>

                <body>
                    <center><table border='1'>
                        <tr><th>Name</th><th>x32</th><th>x64</th><th>v7hl</th><th>v7 vs 32</th><th>v7 vs 64</th></tr>
        """)
        for sorti in sortd:
            keyn = sorti[1]
            if (("i386" in times[keyn].keys()) and ("x86_64" in times[keyn].keys()) and ("armhfp" in times[keyn].keys())):
                print("<tr>")
                print("<td align='right'>%s</td>" % (keyn))
                print("<td align='center'> &nbsp; <a href='http://koji.fedoraproject.org/koji/taskinfo?taskID=%d'>%s</a> &nbsp; </td>" % (times[keyn]["i386"]["id"], times[keyn]["i386"]["elapsed"]))
                print("<td align='center'> &nbsp; <a href='http://koji.fedoraproject.org/koji/taskinfo?taskID=%d'>%s</a> &nbsp; </td>" % (times[keyn]["x86_64"]["id"], times[keyn]["x86_64"]["elapsed"]))
                print("<td align='center'> &nbsp; <a href='http://arm.koji.fedoraproject.org/koji/taskinfo?taskID=%d'>%s</a> &nbsp; </td>" % (times[keyn]["armhfp"]["id"], times[keyn]["armhfp"]["elapsed"]))
                sign = "-"; color = "009933"
                diff = (times[keyn]["armhfp"]["time"] - times[keyn]["i386"]["time"])
                if (diff > 0):
                    sign = "+"; color = "CC0000"
                print("<td align='center'> &nbsp; <span style='color:#%s'>%s%s</span> &nbsp; </td>" % (color, sign, ts2hms(abs(diff)).strip()))
                sign = "-"; color = "009933"
                diff = (times[keyn]["armhfp"]["time"] - times[keyn]["x86_64"]["time"])
                if (diff > 0):
                    sign = "+"; color = "CC0000"
                print("<td align='center'> &nbsp; <span style='color:#%s'>%s%s</span> &nbsp; </td>" % (color, sign, ts2hms(abs(diff)).strip()))
                print("</tr>")
        print("""
                    </table></center>
                </body>
            </html>
        """)

