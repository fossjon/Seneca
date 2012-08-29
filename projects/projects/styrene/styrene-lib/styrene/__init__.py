#!/usr/bin/python -tt
"""Styrene is an experimental database-backed package queueing system
used with koji to solve build ordering problems and to queue and track
package builds."""

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

import cgi
import hashlib
import os
import random
import re
import sqlite3
import string
import subprocess
import sys
import time
import urllib

import koji
import yum
import rpmUtils.miscutils

import webgen
import fixit


# The destination sql db name
DATABASE = "ps.db"

# Default repos
BINARYREPO = "fedora"
SOURCEREPO = "fedora-source"

# Arch for SRPMs
SOURCEARCH = "src"

# Default release (used as $releasever in .repo files)
RELEASE = "12"

# Koji hub url and tag name
KOJIURL = "http://koji.fedoraproject.org"
KOJIHUB = (KOJIURL + "/kojihub")
KOJITAG = ("dist-f" + RELEASE)

# ARM Koji Vars
ARMKOJIURL = "http://arm.koji.fedoraproject.org"
ARMKOJIHUB = (ARMKOJIURL + "/kojihub")

CLIENTCA = (webgen.shellHome() + "/.fedora-upload-ca.cert")
CLIENTCERT = (webgen.shellHome() + "/.fedora.cert")
SERVERCA = (webgen.shellHome() + "/.fedora-server-ca.cert")

# Internally used class variables
sqlconn = None
sqlcurs = None
rpms = None
srpms = None


class styreneBase:
    """Base class for Styrene."""
    
    def prepPkg(self, srpmPkg):
        '''Removes surrounding pkg name info in order to provide "wider" searches.
        
        Return: The cleaned package name.'''
        
        srpmPkg = srpmPkg.strip()
        srpmPkg = re.sub("^[0-9]*:", "", srpmPkg)
        srpmPkg = re.sub("\.src\.rpm$", "", srpmPkg)
        
        return srpmPkg
    
    def inftostr(self, infolist):
        '''Convert the info strings from checkPkg into one nice output string.
        
        Return: The joined/merged strings into one string.'''
        
        outstr = ""
        
        for infoitem in infolist:
            outstr += (infoitem[2] + "\n")
        
        return outstr
    
    def getWebs(self, urls, line=False, html=False):
        '''Read a web page and format it as the user requests.
        
        Return: The requested web page as a string.'''
        
        try:
            urlobjc = urllib.urlopen(urls)
        
        except:
            return ""
        
        urlstri = urlobjc.read()
        
        if ((line == True) or (html == True)):
            urlstri = re.sub("[\t\r\n]", "", urlstri)
            
            if (html == True):
                urlstri = re.sub("<", "\n<", urlstri)
        
        urlobjc.close()
        
        return urlstri
    
    def downloadPkg(self, srpmPkg):
        '''Download the requested source rpm package.
        
        Return: The filename of the stored file.'''
        
        global KOJIURL
        
        srpmPkg = (self.prepPkg(srpmPkg) + ".src.rpm")
        (pkgname, pkgvers, pkgrels, pkgepoch, pkgarch) = rpmUtils.miscutils.splitFilename(srpmPkg)
        fullpkgurl = ("%s/packages/%s/%s/%s/src/%s" % (KOJIURL, pkgname, pkgvers, pkgrels, srpmPkg))
        
        try:
            websobjc = urllib.urlopen(fullpkgurl)
        
        except:
            return (srpmPkg, "")
        
        filename = ("/tmp/" + srpmPkg)
        fileobjc = open(filename, "w")
        
        while (1):
            websdata = websobjc.read(4096)
            
            if (not websdata):
                break
            
            fileobjc.write(websdata)
        
        fileobjc.close()
        websobjc.close()
        
        pipeoutp = subprocess.Popen("rpm -qlp '%s'" % (filename), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
        filelist = pipeoutp.read()
        pipeoutp.close()
        
        if (filelist == ""):
            os.unlink(filename)
            return (srpmPkg, "")
        
        return (srpmPkg, filename)
    
    def readconf(self, filename, confdict):
        """Reads from a config file.
        
        Reads a file line by line (stripping white space).
        Splits each line once on the '=' character.
        Stores the key/value pair in the dictionary.
        Returns: The same (but possibly modified) dictionary."""
        
        try:
            fileobjc = open(filename, "r")
        
        except:
            return confdict
        
        lineread = fileobjc.readline()
        
        while (lineread):
            linelist = lineread.split("=", 1)
            
            if (len(linelist) >= 2):
                linelist[0] = linelist[0].strip().lower()
                linelist[1] = linelist[1].strip()
                confdict[linelist[0]] = linelist[1]
            
            lineread = fileobjc.readline()
        
        return confdict
    
    def formListToStr(self, headlist, datalist):
        '''Given a header list and a data list then output a nice looking string.
        
        Return: The formatted string.'''
        
        linesize = 0
        outpstri = ""
        maxlist = []
        
        try:
            maxcols = int(os.environ["COLUMNS"])
        
        except:
            maxcols = 10000
        
        # Pre-calculate the max padding length for each output column
        
        for x in range(0, len(headlist)):
            maxlist.append(len(headlist[x]))
            
            for dataitem in datalist:
                maxlist[x] = max(maxlist[x], len(dataitem[x]))
            
            # add 4 to reserve room for surrounding spaces & dashes
            
            if ((linesize + maxlist[x] + 4) > maxcols):
                maxlist[x] -= ((linesize + maxlist[x] + 4) - maxcols)
            
            linesize += (maxlist[x] + 4)
        
        outpstri += (("-" * linesize) + "\n")
        
        # Store each column header with padding
        
        for x in range(0, len(headlist)):
            padnum = (maxlist[x] - len(headlist[x]))
            outpstri += ("- " + headlist[x] + (" " * padnum) + " -")
        
        outpstri += "\n"
        
        # Store each package status info with padding
        
        for dataitem in datalist:
            if (dataitem[0] != ""):
                outpstri += (("-" * linesize) + "\n")
            
            for x in range(0, len(headlist)):
                maxlen = maxlist[x]
                colstr = dataitem[x][0:maxlen]
                
                padnum = (maxlen - len(colstr))
                outpstri += ("- " + colstr + (" " * padnum) + " -")
            
            outpstri += "\n"
        
        outpstri += (("-" * linesize) + "\n")
        outpstri = outpstri.strip()
        
        return outpstri
    
    def __init__(self, argsdict = {}):
        """Initialize the class."""
        
        global DATABASE
        global KOJIHUB
        global KOJITAG
        global BINARYREPO
        global SOURCEREPO
        global SOURCEARCH
        global RELEASE
        
        global sqlconn
        global sqlcurs
        global rpms
        global srpms
        
        # Attempt to auto-detect the system release number first
        pipeoutp = subprocess.Popen("cat /etc/*-release /etc/issue* | sed -e 's/.* \\([0-9][0-9]*\\) .*/\\1/g' | grep -i '^[0-9][0-9]*$' | sort | uniq | head -n 1", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
        versstri = pipeoutp.read().strip()
        pipeoutp.close()
        
        try:
            versnumb = int(versstri)
            RELEASE = versstri
            KOJITAG = ("dist-f" + RELEASE)
        
        except:
            pass
        
        # Store the config options in a temp list while processing (set it back later)
        tmpcnfdic = {"db":DATABASE, "kojihub":KOJIHUB, "kojitag":KOJITAG, "binrepo":BINARYREPO, "srcrepo":SOURCEREPO, "srcarch":SOURCEARCH, "release":RELEASE}
        
        # Process the sys wide/user conf files
        tmpcnfdic = self.readconf("/etc/styrene.conf", tmpcnfdic)
        tmpcnfdic = self.readconf(os.environ["HOME"] + "/.styrene.conf", tmpcnfdic)
        
        # Check for any set environment vars
        for dictkey in tmpcnfdic.keys():
            try:
                upperval = os.environ["STYRENE_%s" % dictkey.upper()]
                tmpcnfdic[dictkey] = upperval
            
            except:
                pass
        
        # Set the user arg opts last
        for dictkey in argsdict.keys():
            if (argsdict[dictkey] != ""):
                tmpcnfdic[dictkey] = argsdict[dictkey]
        
        # Set the temp conf list back into the global variables
        DATABASE = tmpcnfdic["db"]
        KOJIHUB = tmpcnfdic["kojihub"]
        KOJITAG = tmpcnfdic["kojitag"]
        BINARYREPO = tmpcnfdic["binrepo"]
        SOURCEREPO = tmpcnfdic["srcrepo"]
        SOURCEARCH = tmpcnfdic["srcarch"]
        RELEASE = tmpcnfdic["release"]
        
        # Database setup
        sqlconn = sqlite3.connect(DATABASE)
        sqlcurs = sqlconn.cursor()
        
        # Set up for RPM and SRPM repo access via yum
        rpms = yum.YumBase()
        rpms.preconf.init_plugins = False
        rpms.preconf.releasever = RELEASE
        rpms.setCacheDir()
        rpms.repos.disableRepo("*")
        rpms.repos.enableRepo(BINARYREPO)
        
        srpms = yum.YumBase()
        srpms.preconf.arch = SOURCEARCH
        srpms.preconf.releasever = RELEASE
        srpms.preconf.init_plugins = False
        srpms.setCacheDir()
        srpms.repos.disableRepo("*")
        srpms.repos.enableRepo(SOURCEREPO)
    
    def dispVars(self):
        """Display out the currently defined variable values."""
        
        global DATABASE
        global KOJIHUB
        global KOJITAG
        global BINARYREPO
        global SOURCEREPO
        global SOURCEARCH
        global RELEASE
        
        global KOJIHUB
        global KOJITAG
        global ARMKOJIHUB
        global CLIENTCA
        global CLIENTCERT
        global SERVERCA
        
        outpstri = ("Database: name=[%s]\n" % (DATABASE))
        outpstri += ("Koji: hub=[%s] tag=[%s]\n" % (KOJIHUB, KOJITAG))
        outpstri += ("Repo: bin=[%s] src=[%s]\n" % (BINARYREPO, SOURCEREPO))
        outpstri += ("Arch: src=[%s]\n" % (SOURCEARCH))
        outpstri += ("Release: num=[%s]\n" % (RELEASE))
        outpstri += "\n"
        outpstri += ("ARM-Koji: hub=[%s]\n" % (ARMKOJIHUB))
        outpstri += ("CA: client=[%s] server=[%s]\n" % (CLIENTCA, SERVERCA))
        outpstri += ("Cert: client=[%s]\n" % (CLIENTCERT))
        
        return outpstri
    
    def createDb(self):
        """Create the SQLite database.
        
        Note: state -> 0 = not built ; 1 = built ; 2 = building ; 3 = expected error ; 4 = unexpected error
        Note: comment -> should be related to some build message regarding the package
        Note: model -> -1 = built ; 0 = not built ; 1 <= dep errors
        
        Creates the SQLite database named 'ps.db' in the current directory.
        Returns: Nothing."""
        
        global sqlconn
        global sqlcurs
        
        try:
            sqlcurs.execute("DROP TABLE goal;")
        except:
            pass
        
        sqlcurs.execute("CREATE TABLE goal (srpm varchar(256) PRIMARY KEY,  \
        envr_original varchar(40),                                          \
        envr_override varchar(40),                                          \
        state int,                                                          \
        timestamp timestamp,                                                \
        model int,                                                          \
        comment varchar(4096));")
        
        try:
            sqlcurs.execute("DROP TABLE dep_cap;")
        except:
            pass
        
        sqlcurs.execute("CREATE TABLE dep_cap (srpm varchar(256), capability varchar(256));")
        
        try:
            sqlcurs.execute("DROP TABLE dep_rpm;")
        except:
            pass
        
        sqlcurs.execute("CREATE TABLE dep_rpm (capability varchar(256) PRIMARY KEY, rpm varchar(256));")
        
        try:
            sqlcurs.execute("DROP TABLE dep_srpm;")
        except:
            pass
        
        sqlcurs.execute("CREATE TABLE dep_srpm (rpm varchar(256) PRIMARY KEY, srpm varchar(256));")
    
    def loadDbENVR(self, srpmPkg):
        """Loads an ENVR goal into the db.
        
        Given an ENVR, populate the db with dependency information.
        Returns: Nothing."""
        
        global sqlconn
        global sqlcurs
        
        if ((sqlconn == None) or (sqlcurs == None)):
            raise NameError("DatabaseConnectionNotOpen")
        
        pkgs = srpms.pkgSack.matchPackageNames([srpmPkg])
        
        print("\n%s" % (srpmPkg))
        
        if (len(pkgs[0])) == 0:
            print("No match.")
        
        else:
            srpm = pkgs[0][0]
            srpmext = (str(srpm) + ".rpm")
            
            print("\tSRPM: %s" % (srpm))
            
            try:
                sqlcurs.execute("INSERT INTO goal (srpm, state, model, comment) VALUES ('%s', 0, 0, '');" % (srpmext))
            
            except:
                pass
            
            # Find the build depdendencies for the SRPM
            # Finds the capability required, then the RPM that provides
            # that capability, then the corresponding SRPM
            
            try:
                deps = srpms.findDeps([srpm])
            
            except:
                print("Error findDeps on %s" % (srpm))
            
            if len(deps[srpm]) == 0:
                print("\tNo BuildRequires")
            
            else:
                print("\tBuildRequires:")
                
                for dep in deps[srpm]:
                    try:
                        rpm = rpms.returnPackageByDep(dep[0])
                    
                    except:
                        pass
                    
                    else:
                        sqlcurs.execute("SELECT count(*) FROM dep_cap WHERE srpm='%s' AND capability='%s'" % (srpmext, dep[0]))        
                        count = next(iter(sqlcurs))[0]        
                        
                        if count == 0:
                                    sqlcurs.execute("INSERT INTO dep_cap VALUES ('%s', '%s');" % (srpmext, dep[0]))
                        
                        rpm_envr = ("%s" % rpm)
                        
                        try:
                            sqlcurs.execute("INSERT INTO dep_rpm VALUES ('%s', '%s');" % (dep[0], rpm_envr))
                        
                        except sqlite3.IntegrityError:
                            pass
                        
                        srpm_envr = ("%s" % rpm.sourcerpm)
                        
                        if int(rpm.epoch) > 0:
                            srpm_envr = ("%s:%s" % (rpm.epoch, srpm_envr))
                        
                        try:
                            sqlcurs.execute("INSERT INTO dep_srpm VALUES ('%s', '%s');" % (rpm_envr, srpm_envr))
                        
                        except sqlite3.IntegrityError:
                            pass
                        
                        print("\t\t%s\n\t\t\tprovided by %s\n\t\t\t\tfrom %s" % (dep[0], rpm_envr, srpm_envr))
    
    def loadDbKoji(self):
        """Loads the DB from the PA Koji.
        
        Loads the entire database from the package list supplied by 
        the remote koji instance.
        Returns: Nothing."""
        
        global KOJIHUB
        global KOJITAG
        
        global sqlconn
        global sqlcurs
        
        if ((sqlconn == None) or (sqlcurs == None)):
            raise NameError("DatabaseConnectionNotOpen")
        
        # Get the list of packages from remote koji
        kojisession = koji.ClientSession(KOJIHUB)
        pkgs = kojisession.listPackages(tagID=KOJITAG, inherited=True)
        
        # Count packages
        pkg_cnt = 0
        
        # Loop through package list
        for pkg in pkgs:
            # Skip if blocked
            if (pkg['blocked']):
                print("%s - blocked" % (pkg["package_name"]))
                continue
            
            # Get builds for that package
            pkginfo = kojisession.listTagged(KOJITAG, inherit=True, package=pkg['package_name'])
            
            # Skip if no builds
            if (len(pkginfo) < 1):
                print("%s - no builds" % (pkg["package_name"]))
                continue
            
            # Find a possible SRPM NVR given the name, querying SRPM repo
            pkgname = pkg['package_name']
            self.loadDbENVR(pkgname)
            
            # Update db
            pkg_cnt += 1
            
            if ((pkg_cnt % 1000) == 0):
                sqlconn.commit()
    
    def markPkgByGlob(self, pkgGlob, stateflag=0, comment=None, envro=None, flush=False):
        """Sets the built flag on a goal SRPM using globbing.
        
        Finds packages patching the pkgGlob and sets the built
        flag to the stateflag value.
        
        Returns: list of pkgs matched, each pkg is 
        (srpm,previouslyBuilt)"""
        
        global sqlconn
        global sqlcurs
        
        fields = ("state = %s" % (stateflag))
        pkglist = []
        
        sqlcurs.execute("SELECT srpm, state FROM goal WHERE srpm GLOB '%s' OR srpm GLOB '[0-9]*:%s';" % (pkgGlob, pkgGlob))
        
        for row in sqlcurs:
            pkglist.append([row[0], row[1]])
        
        if (comment != None):
            fields = ("%s, comment = '%s'" % (fields, comment))
        
        if (envro != None):
            fields = ("%s, envr_override = '%s'" % (fields, envro))
        
        sqlcurs.execute("UPDATE goal SET %s WHERE srpm GLOB '%s' OR srpm GLOB '[0-9]*:%s';" % (fields, pkgGlob, pkgGlob))
        
        if (flush):
            sqlconn.commit()
        
        return pkglist
    
    def listPrevKoji(self, srpmPkg):
        '''Check for the latest version of a package if built.
        
        Arguments: A source RPM package name.
        Return: The package object in a list object.'''
        
        global ARMKOJIHUB
        global KOJITAG
        
        srpmPkg = re.sub("\.src\.rpm$", "", srpmPkg)
        (pkgname, pkgvers, pkgrels, pkgepoch, pkgarch) = rpmUtils.miscutils.splitFilename(srpmPkg)
        armkojisession = koji.ClientSession(ARMKOJIHUB)
        
        # get the latest tagged build info for a pkg if one exists
        pkglist = armkojisession.listTagged(KOJITAG, inherit=True, latest=True, package=pkgname)
        pkgname = ""
        
        if (pkglist):
            pkgname = (pkglist[0]["nvr"] + ".src.rpm")
            
            if (pkglist[0]["epoch"] != None):
                pkgname = (str(pkglist[0]["epoch"]) + ":" + pkgname)
        
        return pkgname
    
    def cleanVers(self, versStri):
        '''Attempt to clean a version string as much as possible.
        
        Arguments: A version string.
        Return: A cleaner version string.'''
        
        letrlist = "abcdefghijklmnopqrstuvwxyz"
        pkgvers = versStri.lower()
        
        for x in range(0, len(letrlist)):
            pkgvers = pkgvers.replace(letrlist[x], "%02d" % (x))
        
        pkgvers = re.sub("[^0-9\.]", "", pkgvers)
        
        return pkgvers
    
    def maxVers(self, versA, versB):
        '''Attempt to compare two version strings.
        
        Arguments: Two version strings.
        Return: The maximum version string.'''
        
        listA = self.cleanVers(versA).split(".")
        listB = self.cleanVers(versB).split(".")
        
        while (len(listA) < len(listB)):
            listA.insert(len(listA) - 1, "0")
        
        while (len(listB) < len(listA)):
            listB.insert(len(listB) - 1, "0")
        
        for x in range(0, len(listA)):
            if (listA[x] == ""):
                listA[x] = "0"
            
            if (listB[x] == ""):
                listB[x] = "0"
            
            if (int(listA[x]) < int(listB[x])):
                return versB
            
            if (int(listA[x]) > int(listB[x])):
                return versA
        
        return versA
    
    def equivPkgKoji(self, srpmPkg):
        '''Attempt to find a built version of the pkg (in the SA) of equal or greater version.
        
        Arguments: A package source RPM name.
        Return: Any satisifying package source RPM.'''
        
        global ARMKOJIHUB
        global KOJITAG
        
        #srpmPkg = re.sub("\.src\.rpm$", "", srpmPkg)
        (pkgname, pkgvers, pkgrels, pkgepoch, pkgarch) = rpmUtils.miscutils.splitFilename(srpmPkg)
        pkgrels = re.sub("\..*$", "", pkgrels)
        armkojisession = koji.ClientSession(ARMKOJIHUB)
        
        if (pkgepoch == ""):
            pkgepoch = "0"
        
        if (pkgrels == ""):
            pkgrels = "0"
        
        origvers = (pkgepoch + "." + pkgvers + "." + pkgrels)
        maxvers = ""
        maxname = ""
        
        # get a list of previously tagged pkgs from koji
        pkgs = armkojisession.listTagged(KOJITAG, inherit=True, package=pkgname)
        
        for pkg in pkgs:
            if (pkg["epoch"] == None):
                pkg["epoch"] = "0"
            
            if (pkg["release"] != None):
                pkg["release"] = re.sub("\..*$", "", pkg["release"])
            
            compname = pkg["package_name"]
            compvers = (str(pkg["epoch"]) + "." + pkg["version"] + "." + pkg["release"])
            
            #print("[%s] orig-ver=[%s] max-ver=[%s] comp-vers=[%s]" % (srpmPkg, origvers, maxvers, compvers))
            tmpmax = self.maxVers(maxvers, compvers)
            
            if (tmpmax != maxvers):
                maxvers = compvers
                maxname = (pkg["nvr"] + ".src.rpm")
                
                if (pkg["epoch"] != "0"):
                    maxname = (str(pkg["epoch"]) + ":" + maxname)
        
        # if we did not find any matches at all then just return now
        if (maxname == ""):
            return ""
        
        tmpmax = self.maxVers(maxvers, origvers)
        
        # if the max version found is < the original then return now
        if (tmpmax != maxvers):
            return ""
        
        # if the max version found is == the original then return now
        if (tmpmax == origvers):
            return ""
        
        return maxname
    
    def convertState(self, stateNumb, srpmPkg):
        '''Convert a koji package state into our local db version.
        
        Note: build-states: None - unbuilt
                               0 - building
                               1 - complete
                               2 - ?
                               3 - failed
                               4 - canceled
        
        Return: The newly converted state number.'''
        
        if (stateNumb != 1):
            # this call is to see if this pkg has ever been built before
            pkgprev = self.listPrevKoji(srpmPkg)
            
            # this call is to see if this pkg has had a newer version of it compiled before
            pkgequiv = self.equivPkgKoji(srpmPkg)
        
        if ((stateNumb != 1) and (pkgprev == "")):
            stateNumb = 3
        
        elif ((stateNumb != 1) and (pkgequiv != "")):
            stateNumb = 1
            self.markPkgByGlob(srpmPkg, comment="", envro=pkgequiv, flush=True)
        
        elif (stateNumb == 0):
            stateNumb = 2
        
        elif (stateNumb == 4):
            stateNumb = 0
        
        elif (stateNumb < 0):
            stateNumb = 0
        
        elif (stateNumb > 1):
            stateNumb = 4
        
        return stateNumb
    
    def listTasksKoji(self, mine=False):
        '''Attempt to resolv a list of currently que'd pkgs.
        
        Note: task-states: 0 - free
                           1 - open
        
        Return: A list containing the pkg name and its state'''
        
        global ARMKOJIURL
        global ARMKOJIHUB
        
        global CLIENTCA
        global CLIENTCERT
        global SERVERCA
        
        armkojisession = koji.ClientSession(ARMKOJIHUB)
        
        if (mine == True):
            armkojisession.ssl_login(CLIENTCERT, CLIENTCA, SERVERCA)
            userid = armkojisession.getLoggedInUser()
            userid = userid['id']
            
            tasklist = armkojisession.taskReport(owner=userid)
        
        else:
            tasklist = armkojisession.taskReport()
        
        pkglist = []
        
        for taskitem in tasklist:
            if (taskitem["parent"] or taskitem["completion_time"]):
                continue
            
            taskurln = ("%s/koji/taskinfo?taskID=%d" % (ARMKOJIURL, taskitem["id"]))
            #taskstate = taskitem["state"]
            taskstate = 2
            
            taskpage = self.getWebs(taskurln, line=True)
            regxobjc = re.match(".*<title>([^<]+)</title>.*", taskpage, re.I)
            
            if (regxobjc):
                taskname = regxobjc.group(1)
                taskname = taskname.replace("build (", "").replace(") | Task Info | Koji", "")
                taskname = re.sub("^[^ ]+ ", "", taskname)
                
                pkglist.append([taskname, taskurln, taskstate])
        
        return pkglist
    
    def checkPkgKoji(self, srpmPkg, local=True, string=True, logs=False):
        """Check a package's status.
        
        Note: srpmPkg - If <local> is true then <srpmPkg> can be globbed.
        
        Arguments: local  - Check the local db or remote build system
                   string - Return a printable string as the output
                   logs   - If remote is specified then get as much log file data as possible
        
        Returns: A pre-formatted string or package list."""
        
        global ARMKOJIURL
        global ARMKOJIHUB
        
        global sqlconn
        global sqlcurs
        
        srpmname = self.prepPkg(srpmPkg)
        headlist = ["Package Name", "Build Status", "Message"]
        pkglist = []
        
        if (local == True):
            sqlcurs.execute("SELECT srpm, state, comment, envr_override FROM goal WHERE srpm GLOB '*%s*';" % (srpmname))
            
            for sqlrowd in sqlcurs:
                srpmname = str(sqlrowd[0])
                statestr = str(sqlrowd[1])
                infolist = str(sqlrowd[2]).split("\n")
                overname = sqlrowd[3]
                
                if (overname):
                    srpmname = ("o:" + str(overname))
                
                for infoitem in infolist:
                    if ((srpmname == "") and (infoitem == "")):
                        continue
                    
                    pkglist.append([srpmname, statestr, infoitem])
                    srpmname = ""
                    statestr = ""
        
        else:
            pkgcomment = ""
            armkojisession = koji.ClientSession(ARMKOJIHUB)
            
            # ask koji for any build information regarding this pkg
            pkgbuild = armkojisession.getBuild(srpmname)
            
            try:
                pkgstate = self.convertState(pkgbuild["state"], srpmname)
            
            except:
                pkgstate = self.convertState(-1, srpmname)
            
            if ((pkgstate == 4) and logs):
                taskid = pkgbuild["task_id"]
                taskpage = self.getWebs("%s/koji/taskinfo?taskID=%d" % (ARMKOJIURL, taskid), line=True)
                tasklist = taskpage.replace("<a", "\n<a").split("\n")
                
                for taskline in tasklist:
                    regxobjc = re.match("<a [^>]*href=\"taskinfo\?taskID=([0-9]+)\"[^>]*>[^<]*armv[^<]*</a>.*", taskline)
                    
                    if (not regxobjc):
                        continue
                    
                    subtaskid = regxobjc.group(1)
                    loglist = ["root.log", "build.log", "state.log", "mock_output.log"]
                    #print("child task ID for [%s]=[%d]" % (srpmname, subtaskid))
                    
                    for logitem in loglist:
                        infopage = self.getWebs("%s/koji/getfile?taskID=%s&name=%s" % (ARMKOJIURL, subtaskid, logitem))
                        
                        if (re.match(".*genericerror: no file [^ ]+ output by task.*", infopage.replace("\n", ""), re.I)):
                            continue
                        
                        infopage = infopage.split("\n")
                        
                        for infoline in infopage:
                            infoline = ("%s: %s" % (logitem, infoline.strip()))
                            
                            if (not infoline):
                                continue
                            
                            pkglist.append([str(srpmPkg), str(pkgstate), str(infoline)])
                            
                            srpmPkg = ""
                            pkgstate = ""
            
            if (srpmPkg != ""):
                pkglist.append([str(srpmPkg), str(pkgstate), str(pkgcomment)])
        
        if (string == True):
            return self.formListToStr(headlist, pkglist)
        
        return pkglist
    
    def buildPkgKoji(self, srpmPkg, filename=None, scratch=False):
        """Submit a pkg to koji for building.
        
        Needs to login, download and submit an srpm file.
        Returns: The koji url task id."""
        
        global KOJITAG
        
        global ARMKOJIURL
        global ARMKOJIHUB
        
        global CLIENTCA
        global CLIENTCERT
        global SERVERCA
        
        # download the srpm file
        if (filename == None):
            (srpmPkg, filename) = self.downloadPkg(srpmPkg)
        
        if (filename == ""):
            #return ("Download error: [%s]" % (srpmPkg))
            return ""
        
        # login into koji since we need auth to build
        armkojisession = koji.ClientSession(ARMKOJIHUB)
        armkojisession.ssl_login(CLIENTCERT, CLIENTCA, SERVERCA)
        
        # setup some koji-build vars and upload/build the srpm package
        serverdir = ("cli-build/%r.%s" % (time.time(), ''.join([random.choice(string.ascii_letters) for i in range(8)])))
        source = ("%s/%s" % (serverdir, srpmPkg))
        opts = {}
        
        if (scratch):
            opts["scratch"] = True
        
        armkojisession.uploadWrapper(filename, serverdir)
        task_id = armkojisession.build(source, KOJITAG, opts, priority=2)
        
        if (task_id < 1):
            #return ("Build error: taskID=%d" % (task_id))
            os.unlink(filename)
            
            return ""
        
        task_st = ("%s/koji/taskinfo?taskID=%d" % (ARMKOJIURL, task_id))
        self.markPkgByGlob(srpmPkg, stateflag=2, comment=task_st, flush=True)
        os.unlink(filename)
        
        return task_st
    
    def listUnbuilt(self):
        '''Get a list of non-built packages.
        
        Args: None.
        Return: The unbuilt list.'''
        
        global sqlconn
        global sqlcurs
        
        pkglist = []
        sqlcurs.execute("SELECT srpm FROM goal WHERE state != 1;")
        
        for sqlrowd in sqlcurs:
            pkglist.append(sqlrowd[0])
        
        return pkglist
    
    def getQueuePass(self):
        """Finds list of packages that could be built now.
        
        Determines the packages for which all build dependencies are now available.
        Returns: list of SRPM ENVRs"""
        
        global sqlconn
        global sqlcurs
        
        sqlcurs.execute("SELECT DISTINCT goal.srpm                                  \
        FROM goal                                                                   \
        WHERE goal.state==0 AND goal.model==0                                       \
        EXCEPT                                                                      \
        SELECT DISTINCT goal.srpm FROM goal                                         \
        JOIN dep_cap ON (goal.srpm==dep_cap.srpm)                                   \
        JOIN dep_rpm ON (dep_cap.capability==dep_rpm.capability)                    \
        JOIN dep_srpm ON (dep_rpm.rpm==dep_srpm.rpm)                                \
        JOIN goal AS built ON (dep_srpm.srpm==built.srpm)                           \
        WHERE built.state!=1 AND built.model>=0;")
        
        result=[]
        for row in sqlcurs:
            result.append(row[0])
        
        return result
    
    def dummyBuildPass(self):
        """Marks all packages that could be built as having been built.
        
        Determines all of the packages that could be built now and marks each of
        them as built. Intended for use in dependency ordering.
        Returns: nothing"""
        
        sqlcurs.execute("UPDATE goal                                                \
        SET model=-1                                                                \
        WHERE srpm IN                                                               \
        (SELECT DISTINCT goal.srpm                                                  \
        FROM goal                                                                   \
        WHERE goal.state==0 AND goal.model==0                                       \
        EXCEPT                                                                      \
        SELECT DISTINCT goal.srpm                                                   \
        FROM goal                                                                   \
        JOIN dep_cap ON (goal.srpm==dep_cap.srpm)                                   \
        JOIN dep_rpm ON (dep_cap.capability==dep_rpm.capability)                    \
        JOIN dep_srpm ON (dep_rpm.rpm==dep_srpm.rpm)                                \
        JOIN goal AS built ON (dep_srpm.srpm==built.srpm)                           \
        WHERE built.state!=1 AND built.model>=0);")
    
    def unbuiltGoalCount(self):
        """Counts unbuilt/unbuildable goals.
        
        Counts goal records (packages) which are currently marked as
        unbuilt.
        Returns: count (integer scalar)"""
        
        sqlcurs.execute("SELECT count(*) FROM goal WHERE state=0 AND model=0;")
        return next(iter(sqlcurs))[0]
    
    def builtGoalCount(self):
        """Counts built/buildable goals.
        
        Counts goal records (packages) which are currently marked as
        built.
        Returns: count (integer scalar)"""
        sqlcurs.execute("SELECT count(*) FROM goal WHERE state=1 OR model=-1;")
        return next(iter(sqlcurs))[0]
    
    def allGoalCount(self):
        """Counts all goals.
        
        Counts goal records (packages) regardless of build status.
        Returns: count (integer scalar)"""
        sqlcurs.execute("SELECT count(*) FROM goal;")
        return next(iter(sqlcurs))[0]
    
    def unbuiltGoalSet(self):
        """Gets list of unbuilt/unbuildable goals.
        
        Returns goal records (packages) which are currently marked as
        unbuilt.
        Returns: list of SRPM names"""
        
        sqlcurs.execute("SELECT srpm, envr_override FROM goal WHERE state=0 AND model=0;")
        result=[]
        
        for row in sqlcurs:
            srpmname = row[0]
            
            if (row[1]):
                srpmname = row[1]
            
            result.append(srpmname)
        
        return result
    
    def builtGoalSet(self):
        """Gets list of built/builable goals.
        
        Returns goal records (packages) which are currently marked as
        built.
        Returns: list of SRPM names"""
        sqlcurs.execute("SELECT srpm FROM goal WHERE state=1 OR model=-1;")
        result=[]
        for row in sqlcurs:
            result.append(row[0])
        
        return result
    
    def getDeps(self, srpmName):
        pkglist = []
        sqlcurs.execute("SELECT goal.srpm,dep_srpm.srpm FROM goal JOIN dep_cap ON dep_cap.srpm = goal.srpm JOIN dep_rpm ON dep_rpm.capability = dep_cap.capability JOIN dep_srpm ON dep_srpm.rpm = dep_rpm.rpm WHERE goal.srpm GLOB '%s';" % (srpmName))
        
        for sqlrow in sqlcurs:
            pkglist.append(sqlrow[0] + " -> " + sqlrow[1])
        
        return pkglist
    
    def visual(self):
        global sqlconn
        global sqlcurs
        
        outstr = ("Content-Type: text/html\r\n\r\n")
        
        webdata = cgi.FieldStorage()
        sn = os.environ["SCRIPT_NAME"]
        #clientid = hashlib.sha256(os.environ["REMOTE_ADDR"]).hexdigest()
        
        # handel ajax requests or page requests here
        
        if ("ajax" in webdata):
            try:
                comdstri = webgen.safeStr(webdata["comd"].value)
                namestri = webgen.safeStr(webdata["name"].value)
            
            except:
                comdstri = ""
                namestri = ""
            
            clientid = hashlib.sha256(namestri).hexdigest()
            
            if (comdstri == "logs"):
                outstr += webgen.procLogs(clientid)
            
            elif (comdstri == "koji"):
                outlist = self.checkPkgKoji(namestri, local=False, string=False, logs=True)
                outstr += self.inftostr(outlist)
            
            elif (comdstri == "mock"):
                webgen.rpmbMock(namestri, self, clientid)
            
            elif (comdstri == "getspec"):
                outstr += webgen.getspec(namestri, self, clientid)
            
            elif (comdstri == "setspec"):
                outstr += webgen.setspec(namestri, webdata["data"].value, clientid)
            
            elif (comdstri == "build"):
                webgen.rpmbKoji(namestri, self, clientid)
        
        else:
            # determine which page should be served
            
            try:
                filestri = webgen.safeStr(webdata["file"].value)
            
            except:
                filestri = "index.html"
            
            # search for and read the file requested
            
            for pathname in sys.path:
                try:
                    fileobjc = file(pathname + "/styrene/www/" + filestri)
                
                except:
                    continue
                
                outstr += fileobjc.read()
                fileobjc.close()
                break
            
            # fill the requested file with data
            
            if (filestri == "index.html"):
                pkgstri = ""
                sqlcurs.execute("SELECT srpm, state, comment, envr_override FROM goal WHERE state > 2 AND comment NOT LIKE '%arch%excl%' ORDER BY state DESC;")
                
                for sqlrow in sqlcurs:
                    pkgname = re.sub("^[0-9]*:", "", sqlrow[0])
                    pkgstate = sqlrow[1]
                    
                    clientid = hashlib.sha256(pkgname).hexdigest()
                    procinfo = webgen.procProc(pkgname, clientid)
                    
                    pkgstri += ("<a href=\"javascript:pkgclick('logs', '%s');\" class=\"state%d\">%s</a> %s <br />\n" % (pkgname, pkgstate, pkgname, procinfo))
                
                outstr = outstr.replace("%", "%%").replace("%%s", "%s")
                outstr = (outstr % (sn, pkgstri, sn))
            
            elif (filestri == "graph.pde"):
                builtlist = ""; worklist = ""; waitlist = ""; errolist = ""
                sqlcurs.execute("SELECT srpm, state FROM goal ORDER BY srpm;")
                
                for sqlrow in sqlcurs:
                    if (sqlrow[1] == 0):
                        waitlist += (", \"" + webgen.safeStr(sqlrow[0]) + "\"")
                    
                    elif (sqlrow[1] == 1):
                        builtlist += (", \"" + webgen.safeStr(sqlrow[0]) + "\"")
                    
                    elif (sqlrow[1] == 2):
                        worklist += (", \"" + webgen.safeStr(sqlrow[0]) + "\"")
                    
                    else:
                        errolist += (", \"" + webgen.safeStr(sqlrow[0]) + "\"")
                
                outstr = outstr.replace("%", "%%").replace("%%s", "%s")
                outstr = (outstr % (builtlist[2:], worklist[2:], waitlist[2:], errolist[2:]))
        
        return outstr
    
    def fixBridge(self, srpmName):
        fixit.autopatch(srpmName)
    
    def closeDb(self):
        """Closes the SQLite database connections."""
        
        global sqlconn
        global sqlcurs
        
        if ((sqlconn == None) or (sqlcurs == None)):
            return -1
        
        sqlconn.commit()
        
        sqlcurs.close()
        sqlconn.close()

