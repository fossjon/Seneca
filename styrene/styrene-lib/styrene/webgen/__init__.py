import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time

import rpmUtils.miscutils


# define pre-pre vars

dbfile = "/tmp/unknown.styrene.web.db"


# define pre-run methods

def shellHome():
    global dbfile
    
    comdstri = ("whoami")
    pipeoutp = subprocess.Popen(comdstri, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    username = pipeoutp.read().strip()
    pipeoutp.close()
    
    comdstri = ("id -u")
    pipeoutp = subprocess.Popen(comdstri, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    usernumb = pipeoutp.read().strip()
    pipeoutp.close()
    
    comdstri = ("cat /etc/passwd | grep '^%s:' | awk -F ':' '{ print $6 }'" % (username))
    pipeoutp = subprocess.Popen(comdstri, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    homedir = pipeoutp.read().strip()
    pipeoutp.close()
    
    dbfile = ("/tmp/" + username + ".styrene.web.db")
    
    os.environ["PATH"] = "/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin"
    
    if (username):
        os.environ["USER"] = username
        os.environ["LOGNAME"] = username
    
    if (usernumb):
        os.environ["UID"] = usernumb
        os.environ["EUID"] = usernumb
    
    if (homedir):
        os.environ["HOME"] = homedir
    
    return os.environ["HOME"]

def createDb():
    global dbfile
    
    sqlconn = sqlite3.connect(dbfile)
    sqlcurs = sqlconn.cursor()
    
    try:
        sqlcurs.execute("CREATE TABLE webslogs (websiden VARCHAR(1024), logsdata VARCHAR(4096));")
        sqlcurs.execute("CREATE TABLE websproc (srpmname VARCHAR(1024) PRIMARY KEY, websiden VARCHAR(1024), procnumb INT, procdata VARCHAR(4096));")
    
    except:
        pass
    
    sqlconn.commit()
    
    sqlcurs.close()
    sqlconn.close()


homedir = shellHome()
createDb()

outpref = "[styrene] "
rpmbdir = (homedir + "/rpmbuild")


# package building methods

def safeStr(inptstri):
    '''Attempts to sanitize input strings that are safer for db usage.
    
    Return: The cleaned input string.'''
    
    inptstri = inptstri.replace("\t", "")
    inptstri = inptstri.replace("\r", "")
    inptstri = inptstri.replace("\n", "")
    inptstri = re.sub("[^0-9A-Za-z ~!@#$%^&*_=+;:,.-]", "", inptstri)
    
    return inptstri

def procLogs(uniqId, clearfile=False, logsline=None):
    global dbfile
    
    sqlconn = sqlite3.connect(dbfile)
    sqlcurs = sqlconn.cursor()
    
    if (clearfile == True):
        sqlcurs.execute("DELETE FROM webslogs WHERE websiden = '%s';" % (uniqId))
    
    if (logsline != None):
        timestamp = ("[%s] " % (time.strftime("%H:%M:%S")))
        logswrite = (timestamp + safeStr(logsline))
        sqlcurs.execute("INSERT INTO webslogs (websiden, logsdata) VALUES ('%s', '%s');" % (uniqId, logswrite))
    
    outpdata = ""
    sqlcurs.execute("SELECT logsdata FROM webslogs WHERE websiden = '%s';" % (uniqId))
    
    for sqlrow in sqlcurs:
        outpdata += (sqlrow[0] + "\n")
    
    sqlconn.commit()
    
    sqlcurs.close()
    sqlconn.close()
    
    return outpdata

def insrProc(srpmName, uniqId, procline):
    global dbfile
    
    sqlconn = sqlite3.connect(dbfile)
    sqlcurs = sqlconn.cursor()
    
    procnumb = -1
    procdata = ""
    sqlcurs.execute("SELECT procnumb, procdata FROM websproc WHERE srpmname = '%s' AND websiden = '%s';" % (srpmName, uniqId))
    
    for sqlrow in sqlcurs:
        procnumb = sqlrow[0]
        procdata = sqlrow[1]
    
    if (procnumb < 0):
        sqlcurs.execute("DELETE FROM websproc WHERE srpmname = '%s' AND websiden = '%s';" % (srpmName, uniqId))
        sqlcurs.execute("INSERT INTO websproc (srpmname, websiden, procnumb, procdata) VALUES ('%s', '%s', %d, ' %s ');" % (srpmName, uniqId, -1, procline))
        sqlconn.commit()
    
    sqlcurs.close()
    sqlconn.close()

def procProc(srpmName, uniqId, procline=None):
    global dbfile
    
    sqlconn = sqlite3.connect(dbfile)
    sqlcurs = sqlconn.cursor()
    
    # look for a stored process number
    
    procnumb = -1
    procdata = ""
    procread = ""
    sqlcurs.execute("SELECT procnumb, procdata FROM websproc WHERE srpmname = '%s' AND websiden = '%s';" % (srpmName, uniqId))
    
    for sqlrow in sqlcurs:
        procnumb = sqlrow[0]
        procdata = sqlrow[1]
    
    if (procnumb > 0):
        # look for a running process given a stored process number
        
        shellcmd = ("ps aux | grep -i '^[^ ][^ ]*[ ][ ]*%d[ ][ ]*.*$'" % (procnumb))
        pipeobjc = subprocess.Popen(shellcmd, shell=True, stdout=subprocess.PIPE).stdout
        procread = pipeobjc.read().strip()
        pipeobjc.close()
        
        if (procread == ""):
            # if no process exists anymore then delete the related process entry
            sqlcurs.execute("DELETE FROM websproc WHERE srpmname = '%s' AND websiden = '%s';" % (srpmName, uniqId))
            sqlconn.commit()
    
    if (procline != None):
        # if we are requested to start a new process then check parameters now
        
        if (procread != ""):
            # if a process already exists then exit now
            sqlcurs.close()
            sqlconn.close()
            
            sys.exit(0)
        
        procnumb = os.fork()
        
        if (procnumb != 0):
            # if this is the parent fork process then write and exit now
            
            sqlcurs.execute("DELETE FROM websproc WHERE srpmname = '%s' AND websiden = '%s';" % (srpmName, uniqId))
            sqlcurs.execute("INSERT INTO websproc (srpmname, websiden, procnumb, procdata) VALUES ('%s', '%s', %d, ' %s ');" % (srpmName, uniqId, procnumb, procline))
            sqlconn.commit()
            
            sqlcurs.close()
            sqlconn.close()
            
            sys.exit(0)
    
    sqlcurs.close()
    sqlconn.close()
    
    return procdata

def runcmd(comdstri, runId):
    shellcmd = ("Shell Exec [%s]" % (comdstri))
    procLogs(runId, logsline=shellcmd)
    pipeoutp = subprocess.Popen(comdstri, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
    
    while (1):
        lineread = pipeoutp.readline()
        
        if (not lineread):
            break
        
        lineread = lineread.strip()
        procLogs(runId, logsline=lineread)
    
    pipeoutp.close()

def findfile(dirpath, fileregx):
    outpfile = ""
    retrynum = 0
    
    while (retrynum < 10):
        try:
            dirlist = os.listdir(dirpath)
        
        except:
            break
        
        if (len(dirlist) < 1):
            retrynum += 1
            time.sleep(1)
            continue
        
        for diritem in dirlist:
            if (re.match("^%s$" % (fileregx), diritem, re.I)):
                outpfile = diritem
        
        break
    
    return outpfile

def rpmbSetup(srpmName, styreneObj, setupId, override=0):
    global outpref
    global rpmbdir
    
    if (override == 0):
        procProc(srpmName, setupId, procline=" [ rpmbuild setup ] ")
    
    logsstri = ("%s--- LOCAL SETUP [%s] ---" % (outpref, srpmName))
    procLogs(setupId, clearfile=True, logsline=logsstri)
    (srpmName, filename) = styreneObj.downloadPkg(srpmName)
    
    shellcmd = ("rpm -i '%s'" % (filename))
    runcmd(shellcmd, setupId)
    os.unlink(filename)
    
    procLogs(setupId, logsline=" ")

def rpmbMock(srpmName, styreneObj, mockId, override=0):
    global outpref
    global rpmbdir
    
    if (override == 0):
        procProc(srpmName, mockId, procline=" [ rpmbuild mock ] ")
    
    logsstri = ("%s--- LOCAL MOCK [%s] ---" % (outpref, srpmName))
    procLogs(mockId, clearfile=True, logsline=logsstri)
    (pkgname, pkgvers, pkgrels, pkgepoch, pkgarch) = rpmUtils.miscutils.splitFilename(srpmName)
    
    # check for a spec file
    
    specdir = ("%s/SPECS" % (rpmbdir))
    specfile = findfile(specdir, "%s.*\.spec" % (pkgname))
    
    if (specfile == ""):
        rpmbSetup(srpmName, styreneObj, mockId, override=1)
        specfile = findfile(specdir, "%s.*\.spec" % (pkgname))
    
    # put together a source rpm
    
    shellcmd = ("rpmbuild -bs %s/%s" % (specdir, specfile))
    runcmd(shellcmd, mockId)
    
    # run a mock build
    
    srpmdir = ("%s/SRPMS" % (rpmbdir))
    srpmfile = findfile(srpmdir, "%s.*\.src\.rpm" % (pkgname))
    
    shellcmd = ("mock -v rebuild %s/%s" % (srpmdir, srpmfile))
    runcmd(shellcmd, mockId)
    
    procLogs(mockId, logsline=" ")

def rpmbKoji(srpmName, styreneObj, kojiId, override=0):
    global outpref
    global rpmbdir
    
    if (override == 0):
        procProc(srpmName, kojiId, procline=" [ rpmbuild koji ] ")
    
    logsstri = ("%s--- REMOTE KOJI [%s] ---" % (outpref, srpmName))
    procLogs(kojiId, clearfile=True, logsline=logsstri)
    (pkgname, pkgvers, pkgrels, pkgepoch, pkgarch) = rpmUtils.miscutils.splitFilename(srpmName)
    
    # try to find a source RPM file
    
    srpmdir = ("%s/SRPMS" % (rpmbdir))
    srpmfile = findfile(srpmdir, "%s.*\.src\.rpm" % (pkgname))
    
    if (srpmfile == ""):
        rpmbMock(srpmName, styreneObj, kojiId, override=1)
        srpmfile = findfile(srpmdir, "%s.*\.src\.rpm" % (pkgname))
    
    # que the source RPM pkg for build
    
    srpmpath = ("%s/%s" % (srpmdir, srpmfile))
    linktext = styreneObj.buildPkgKoji(srpmfile, filename=srpmpath, scratch=True)
    
    if (linktext):
        logsstri = ("%s<a href=\"%s\">%s</a>" % (outpref, linktext, linktext))
        procLogs(kojiId, logsline=logsstri)
    
    procLogs(kojiId, logsline=" ")

def getspec(srpmName, styreneObj, specId):
    global outpref
    global rpmbdir
    
    (pkgname, pkgvers, pkgrels, pkgepoch, pkgarch) = rpmUtils.miscutils.splitFilename(srpmName)
    
    # try to find a spec file
    
    specdir = ("%s/SPECS" % (rpmbdir))
    specfile = findfile(specdir, "%s.*\.spec" % (pkgname))
    
    if (specfile == ""):
        rpmbSetup(srpmName, styreneObj, specId)
        specfile = findfile(specdir, "%s.*\.spec" % (pkgname))
    
    # read the spec file
    
    try:
        fileobjc = open("%s/%s" % (specdir, specfile), "r")
        filedata = fileobjc.read()
        fileobjc.close()
        
        timestri = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())
        insrProc(srpmName, specId, " [ spec file edit request -- " + timestri + " ] ")
    
    except:
        filedata = ("Could not read spec file [%s]" % (specfile))
    
    return filedata

def setspec(srpmName, filedata, specId):
    global outpref
    global rpmbdir
    
    (pkgname, pkgvers, pkgrels, pkgepoch, pkgarch) = rpmUtils.miscutils.splitFilename(srpmName)
    
    # try to find a spec file
    
    specdir = ("%s/SPECS" % (rpmbdir))
    specfile = findfile(specdir, "%s.*\.spec" % (pkgname))
    
    if (specfile == ""):
        return ("Could not find any spec file [%s*.spec]" % (pkgname))
    
    try:
        fileobjc = open("%s/%s" % (specdir, specfile), "w")
        fileobjc.write(filedata)
        fileobjc.close()
        
        timestri = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())
        insrProc(srpmName, specId, " [ spec file save request -- " + timestri + " ] ")
    
    except:
        return ("Could not write spec file [%s]" % (specfile))
    
    return filedata

