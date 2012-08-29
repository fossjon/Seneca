import os
import re
import shutil
import subprocess
import sys

import koji
import rpmUtils.miscutils

def p(l):
    for x in range(0, len(l)):
        print(str(x + 1) + ":" + str(l[x]).strip("\r").strip("\n"))
    print("---")

condmach = ["^%if.*$", "^%endif.*$"]
pachmach = ["^([0-9,]*)([acd])$", "^\.$"]

def safenumb(numbstri):
    try:
        numblist = numbstri.split(",")
        
        try:
            return [int(numblist[0]), int(numblist[1])]
        
        except:
            return [int(numblist[0]), int(numblist[0])]
    
    except:
        return [0, 0]

def blocproc(blocflag, testline, testlist, s):
    while (len(blocflag) < 2):
        blocflag.append(0)
    
    a = ((0 + s) % 2)
    b = ((1 + s) % 2)
    blocflag[1] = 0
    
    regxobjc = re.match(testlist[a], testline)
    
    if ((blocflag[0] == 0) and regxobjc):
        blocflag[0] = 1
        blocflag[1] = 1
    
    regxobjc = re.match(testlist[b], testline)
    
    if ((blocflag[0] == 1) and regxobjc):
        blocflag[0] = 0
        blocflag[1] = 1
    
    # make sure to catch state changes if the line itself needs to be included in processing
    return blocflag

def speccond(speclist):
    # make a boolean based map array of where conditional blocks lay
    global condmach
    
    inifflag = []; condlist = []
    
    condlist.append(0)
    
    for lineitem in speclist:
        testline = lineitem.strip()
        inifflag = blocproc(inifflag, testline, condmach, 0)
        
        if ((inifflag[0] == 0) and (inifflag[1] == 1)):
            # include the last line in an if block
            condlist.append(1)
            continue
        
        condlist.append(inifflag[0])
    
    return condlist

def pachtran(pachlist):
    # transform multi-patch blocks into single-patch blocks
    global pachmach
    
    blocflag = []; outplist = []
    addsflag = 0; addslist = []
    chgsflag = 0; chgslist = []
    
    for pachitem in pachlist:
        testline = pachitem.strip()
        saveline = pachitem
        
        blocflag = blocproc(blocflag, testline, pachmach, 0)
        
        if ((blocflag[0] == 1) and (blocflag[1] == 1)):
            # the start of a patch block
            regxobjc = re.match(pachmach[0], testline)
            linemode = regxobjc.group(2)
            linenumb = safenumb(regxobjc.group(1))
            
            if (linemode == "a"):
                addsflag = 1; addslist = [linenumb[0]]
            
            if (linemode == "c"):
                chgsflag = 1; chgslist = [[linenumb[0], linenumb[1]]]
            
            if (linemode == "d"):
                for y in range(linenumb[1], linenumb[0] - 1, -1):
                    outplist.append(str(y) + "d\n")
                # turn off a delete-patch block since it contains no data
                blocflag[0] = 0
        
        if ((blocflag[0] == 1) and (blocflag[1] == 0)):
            # inside the middle of a patch block
            if (addsflag == 1):
                addslist.append(saveline)
            if (chgsflag == 1):
                chgslist.append(saveline)
        
        if ((blocflag[0] == 0) and (blocflag[1] == 1)):
            # the end of a patch block
            if (addsflag == 1):
                for y in range(len(addslist) - 1, 0, -1):
                    outplist.append(str(addslist[0]) + "a\n")
                    outplist.append(addslist[y])
                    outplist.append(".\n")
                    # do not need to decrease append index as it shifts every line down one (in this reverse loop) before inserting
                addsflag = 0; addslist = []
            if (chgsflag == 1):
                while ((len(chgslist) - 1) < (chgslist[0][1] - chgslist[0][0] + 1)):
                    chgslist.append("\n")
                for y in range(len(chgslist) - 1, 0, -1):
                    outplist.append(str(chgslist[0][1]) + "c\n")
                    outplist.append(chgslist[y])
                    outplist.append(".\n")
                    chgslist[0][1] -= 1
                chgsflag = 0; chgslist = []
    
    return outplist

def pachshif(pachlist, stopvalu, shifnumb):
    # increase all the patch line numbers before this by 1
    tempflag = []
    
    for y in range(0, stopvalu):
        if (pachlist[y] == None):
            continue
        
        templine = pachlist[y].strip()
        
        tempflag = blocproc(tempflag, templine, pachmach, 0)
        
        if ((tempflag[0] == 1) and (tempflag[1] == 1)):
            # start of a temp edit block
            regxobjc = re.match(pachmach[0], templine)
            tempmode = regxobjc.group(2)
            tempnumb = safenumb(regxobjc.group(1))
            
            pachlist[y] = (str(tempnumb[0] + shifnumb) + tempmode + "\n")
    
    return pachlist

def pachinsr(pachlist, speclist):
    # insert patch lines containing conditional statements
    global condmach
    global pachmach
    
    blocflag = []; outplist = []
    
    for x in range(0, len(pachlist)):
        if (pachlist[x] == None):
            continue
        
        testline = pachlist[x].strip()
        
        blocflag = blocproc(blocflag, testline, pachmach, 0)
        
        if ((blocflag[0] == 1) and (blocflag[1] == 1)):
            # the start of a patch block
            regxobjc = re.match(pachmach[0], testline)
            linemode = regxobjc.group(2)
            linenumb = safenumb(regxobjc.group(1))
            
            if (linemode == "a"):
                # check to see if this append-patch line is a conditional statement
                if (re.match("(" + condmach[0] + "|" + condmach[1] + ")", pachlist[x + 1])):
                    # insert the conditional line into the spec file list and truncate this append-patch block
                    speclist.insert(linenumb[0], pachlist[x + 1])
                    pachlist[x] = None; pachlist[x + 1] = None; pachlist[x + 2] = None
                    
                    pachlist = pachshif(pachlist, x, 1)
                    blocflag = []
            
            elif (linemode == "c"):
                # check to see if this change-patch line is a conditional statement
                if (re.match("(" + condmach[0] + "|" + condmach[1] + ")", pachlist[x + 1])):
                    # replace the conditional line into the spec file list and truncate this change-patch block
                    speclist[linenumb[0]] = pachlist[x + 1]
                    pachlist[x] = None; pachlist[x + 1] = None; pachlist[x + 2] = None
                    
                    pachlist = pachshif(pachlist, x, 0)
                    blocflag = []
            
            elif (linemode == "d"):
                # check to see if this delete-spec line is a conditional statement
                if (re.match("(" + condmach[0] + "|" + condmach[1] + ")", speclist[linenumb[0]])):
                    # delete the conditional line into the spec file list and truncate this delete-patch block
                    speclist.pop(linenumb[0])
                    pachlist[x] = None
                    
                    pachlist = pachshif(pachlist, x, -1)
                    blocflag = []
    
    for lineitem in pachlist:
        if (lineitem != None):
            outplist.append(lineitem)
    
    return (speclist, outplist)

def pachfilt(pachlist, condlist):
    # filter out unwanted changes in the patch file list
    global pachmach
    
    blocflag = []; outplist = []
    truncflg = 0
    
    for x in range(0, len(pachlist)):
        testline = pachlist[x].strip()
        saveline = pachlist[x]
        
        blocflag = blocproc(blocflag, testline, pachmach, 0)
        
        if ((blocflag[0] == 1) and (blocflag[1] == 1)):
            # the start of a patch block
            regxobjc = re.match(pachmach[0], testline)
            linemode = regxobjc.group(2)
            linenumb = safenumb(regxobjc.group(1))
            
            # remove any changes that are not made to conditional block statements
            if (linemode == "a"):
                if (condlist[linenumb[0]] == 0):
                    truncflg = 1
            
            elif (linemode == "c"):
                if (condlist[linenumb[0]] == 0):
                    truncflg = 1
            
            elif (linemode == "d"):
                if (condlist[linenumb[0]] == 0):
                    saveline = None
                # turn off a delete-patch block since it contains no data
                blocflag[0] = 0
        
        if (truncflg == 1):
            saveline = None
        
        if ((blocflag[0] == 0) and (blocflag[1] == 1)):
            # the end of a patch block
            if (truncflg == 1):
                truncflg = 0
        
        if (saveline != None):
            outplist.append(saveline)
    
    return outplist

def setuppkg(pkgname):
    # get pkg info
    
    kojisess = koji.ClientSession("http://koji.fedoraproject.org/kojihub")
    pkglist = kojisess.listTagged("dist-f13-updates", inherit=True, latest=True, package=pkgname)
    newrpm = pkglist[0]["nvr"]
    (newpkgname, newpkgvers, newpkgrels, newpkgepoch, newpkgarch) = rpmUtils.miscutils.splitFilename(newrpm)
    
    kojisess = koji.ClientSession("http://arm.koji.fedoraproject.org/kojihub")
    pkglist = kojisess.listTagged("dist-f13", inherit=True, latest=True, package=pkgname)
    oldrpm = pkglist[0]["nvr"]
    (oldpkgname, oldpkgvers, oldpkgrels, oldpkgepoch, oldpkgarch) = rpmUtils.miscutils.splitFilename(oldrpm)
    
    # setup dirs
    
    pipe = subprocess.Popen("whoami", shell=True, stdout=subprocess.PIPE).stdout
    name = pipe.read().strip()
    pipe.close()
    
    os.system("mkdir -p /tmp/pkg." + name)
    os.chdir("/tmp/pkg." + name)
    os.system("rm -f *spec* *patch*")
    
    # download pkg files
    
    os.system("if [ ! -f '%s.src.rpm' ] ; then koji download-build --arch=src '%s' ; fi" % (newrpm, newrpm))
    os.system("rpmdev-wipetree > /dev/null ; rpm -i '%s.src.rpm' 2> /dev/null ; cp ~/rpmbuild/SPECS/*.spec ~/rpmbuild/SPECS/tmp.spec.old" % (newrpm))
    
    os.system("if [ ! -f '%s.src.rpm' ] ; then arm-koji download-build --arch=src '%s' ; fi" % (oldrpm, oldrpm))
    os.system("rpm2cpio '%s.src.rpm' | cpio -i '*.spec' 2> /dev/null" % (oldrpm))
    
    # generate initial diff patch file
    
    os.system("diff -e ~/rpmbuild/SPECS/*.spec *.spec > pkg.patch")

def autopatch(pkgname):
    setuppkg(pkgname)
    
    # get the filenames
    
    pipeobjc = subprocess.Popen("echo ~/rpmbuild/SPECS/*.spec", shell=True, stdout=subprocess.PIPE).stdout
    specfile = pipeobjc.read().strip()
    pipeobjc.close()
    
    pipeobjc = subprocess.Popen("echo *.patch", shell=True, stdout=subprocess.PIPE).stdout
    pachfile = pipeobjc.read().strip()
    pipeobjc.close()
    
    # read the files
    
    fileobjc = open(specfile, "r")
    speclist = fileobjc.readlines()
    fileobjc.close()
    
    pachobjc = open(pachfile, "r")
    pachlist = pachobjc.readlines()
    pachobjc.close()
    
    # proc the files
    
    patrlist = pachtran(pachlist)#;p(patrlist)
    (spinlist, painlist) = pachinsr(patrlist, speclist)#;p(painlist)
    spcolist = speccond(spinlist)
    pafilist = pachfilt(painlist, spcolist)
    pafilist.append("wq " + specfile + "\n")#;p(pafilist)
    
    # write the files
    
    fileobjc = open(specfile, "w")
    for lineitem in spinlist:
        fileobjc.write(lineitem)
    fileobjc.close()
    
    fileobjc = open(pachfile, "w")
    for lineitem in pafilist:
        fileobjc.write(lineitem)
    fileobjc.close()
    
    # finalize the changes
    
    os.system("cat '%s' | ed '%s' 2> /dev/null" % (pachfile, specfile))
    os.system("echo ; echo ~/rpmbuild/SPECS/*.spec ; echo --- ; diff -e ~/rpmbuild/SPECS/tmp.spec.old ~/rpmbuild/SPECS/*.spec")

