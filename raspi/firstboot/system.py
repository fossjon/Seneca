import md5
import re
import gtk

from firstboot.config import *
from firstboot.constants import *
from firstboot.functions import *
from firstboot.module import *

import gettext
_ = lambda x: gettext.ldgettext("firstboot", x)
N_ = lambda x: x

import subprocess

class moduleClass(Module):
    def __init__(self):
        Module.__init__(self)
        self.priority = 103
        self.sidebarTitle = N_("System Settings")
        self.title = N_("System Settings")
        self.icon = "workstation.png"

        self.hostfile = "/etc/sysconfig/network"
        self.hostpref = "HOSTNAME="
        self.gtarget = "/lib/systemd/system/graphical.target"
        self.ttarget = "/lib/systemd/system/multi-user.target"
        self.default = "/etc/systemd/system/default.target"
        self.bootdir = "/boot"
        self.memsplit = []
        self.conflist = []

    def apply(self, interface, testing=False):
        hosttext = self.hostname.get_text();

        if (hosttext):
            try:
                fileobjc = open(self.hostfile, "r")
                linelist = fileobjc.readlines()
                fileobjc.close()

                hostleng = len(self.hostpref)
                fileobjc = open(self.hostfile, "w")

                for lineread in linelist:
                    if (lineread[:hostleng] == self.hostpref):
                        lineread = (self.hostpref + hosttext + "\n")
                    fileobjc.write(lineread)

                fileobjc.close()

                subprocess.call(["hostname", hosttext])

            except:
                return RESULT_FAILURE

            try:
                os.unlink(self.default)
            except:
                pass

        if (self.graphic.get_active()):
            try:
                os.symlink(self.gtarget, self.default)
            except:
                pass
        else:
            try:
                os.symlink(self.ttarget, self.default)
            except:
                pass

        for memitem in self.memsplit:
            if (memitem[0].get_active()):
                try:
                    os.unlink(self.bootdir + "/start.elf")
                except:
                    pass

                try:
                    sobj = open(self.bootdir + "/" + memitem[1], "r")
                    dobj = open(self.bootdir + "/start.elf", "w")
                    sstr = sobj.read()
                    dobj.write(sstr)
                    dobj.close()
                    sobj.close()
                except:
                    pass

        for confitem in self.conflist:
            if (confitem[0].get_active()):
                try:
                    os.unlink(self.bootdir + "/config.txt")
                except:
                    pass

                try:
                    sobj = open(self.bootdir + "/" + confitem[1], "r")
                    dobj = open(self.bootdir + "/config.txt", "w")
                    sstr = sobj.read()
                    dobj.write(sstr)
                    dobj.close()
                    sobj.close()
                except:
                    pass

        return RESULT_SUCCESS

    def createScreen(self):
        self.vbox = gtk.VBox(spacing=0)

        table = gtk.Table(16, 3)
        table.set_row_spacings(0)
        table.set_col_spacings(0)

        label = gtk.Label(_(" "))
        label.set_line_wrap(False)
        label.set_alignment(0.0, 0.0)
        table.attach(label, 2, 3, 0, 1, gtk.EXPAND, gtk.SHRINK)

        label = gtk.Label(_("Set a hostname for this computer and choose whether you'd like a graphical or text boot mode."))
        label.set_line_wrap(False)
        label.set_alignment(0.0, 0.0)
        table.attach(label, 0, 3, 1, 2, gtk.FILL, gtk.SHRINK)

        label = gtk.Label(_(" "))
        label.set_line_wrap(False)
        label.set_alignment(0.0, 0.0)
        table.attach(label, 2, 3, 2, 3, gtk.EXPAND, gtk.SHRINK)

        label = gtk.Label(_("Hostname:   "))
        label.set_line_wrap(False)
        label.set_alignment(0.0, 0.0)
        table.attach(label, 0, 1, 4, 5, gtk.FILL, gtk.SHRINK)

        self.hostname = gtk.Entry()
        table.attach(self.hostname, 1, 2, 4, 5, gtk.FILL, gtk.SHRINK)

        label = gtk.Label(_("Boot Type:  "))
        label.set_line_wrap(False)
        label.set_alignment(0.0, 0.0)
        table.attach(label, 0, 1, 5, 6, gtk.FILL, gtk.SHRINK)

        self.graphic = gtk.RadioButton(None, "Graphical")
        self.graphic.set_active(True)
        table.attach(self.graphic, 1, 2, 5, 6, gtk.FILL, gtk.SHRINK)

        label = gtk.Label(_(" "))
        label.set_line_wrap(False)
        label.set_alignment(0.0, 0.0)
        table.attach(label, 0, 1, 6, 7, gtk.FILL, gtk.SHRINK)

        self.plain = gtk.RadioButton(self.graphic, "Text")
        table.attach(self.plain, 1, 2, 6, 7, gtk.FILL, gtk.SHRINK)

        rownumb = 7

        label = gtk.Label(_(" "))
        label.set_line_wrap(False)
        label.set_alignment(0.0, 0.0)
        table.attach(label, 0, 3, rownumb, rownumb + 1, gtk.FILL, gtk.SHRINK)
        rownumb += 1

        label = gtk.Label(_("Memory Split:  "))
        label.set_line_wrap(False)
        label.set_alignment(0.0, 0.0)
        table.attach(label, 0, 1, rownumb, rownumb + 1, gtk.FILL, gtk.SHRINK)

        startmd5 = ""
        try:
            fileobj = open(self.bootdir + "/start.elf", "r")
            filestr = fileobj.read()
            fileobj.close()
            startmd5 = md5.md5(filestr).hexdigest()
        except:
            pass

        desclist = []
        try:
            fileobj = open(self.bootdir + "/start.elf.desc", "r")
            desclist = fileobj.readlines()
            fileobj.close()
        except:
            pass

        oldrow = rownumb

        memobj = None
        for bootitem in os.listdir(self.bootdir):
            regobj = re.match("^arm([0-9]+)_start.elf$", bootitem)
            if (regobj):
                gpunum = str(256 - int(regobj.group(1)))
                descstr = (regobj.group(1) + "MB Linux / " + gpunum + " MB GPU")
                for descitem in desclist:
                    regobj = re.match("^[ \t]*" + bootitem + "[ \t]*:[ \t]*(.*)", descitem, re.I)
                    if (regobj):
                        descstr += (" (" + regobj.group(1) + ") ")
                memobj = gtk.RadioButton(memobj, descstr)
                try:
                    fileobj = open(self.bootdir + "/" + bootitem, "r")
                    filestr = fileobj.read()
                    fileobj.close()
                    elfmd5 = md5.md5(filestr).hexdigest()
                    if (elfmd5 == startmd5):
                        memobj.set_active(True)
                except:
                    pass
                self.memsplit.append([memobj, bootitem])
                table.attach(memobj, 1, 2, rownumb, rownumb + 1, gtk.FILL, gtk.SHRINK)
                rownumb += 1
        if (rownumb == oldrow):
            rownumb += 1

        label = gtk.Label(_(" "))
        label.set_line_wrap(False)
        label.set_alignment(0.0, 0.0)
        table.attach(label, 0, 3, rownumb, rownumb + 1, gtk.FILL, gtk.SHRINK)
        rownumb += 1

        label = gtk.Label(_("Video Configuration:  "))
        label.set_line_wrap(False)
        label.set_alignment(0.0, 0.0)
        table.attach(label, 0, 1, rownumb, rownumb + 1, gtk.FILL, gtk.SHRINK)

        oldrow = rownumb

        confmd5 = ""
        try:
            fileobj = open(self.bootdir + "/config.txt", "r")
            filestr = fileobj.read()
            fileobj.close()
            confmd5 = md5.md5(filestr).hexdigest()
        except:
            pass

        memobj = None
        for bootitem in os.listdir(self.bootdir):
            regobj = re.match("^config.txt..+$", bootitem)
            if (regobj):
                title = ""
                desc = ""
                try:
                    fileobj = open(self.bootdir + "/" + bootitem, "r")
                    for lineread in fileobj.readlines():
                        regobj = re.match("^#[ \t]*title[ \t]*:*[ \t]*(.*)$", lineread.strip(), re.I)
                        if (regobj):
                            title = regobj.group(1)
                        regobj = re.match("^#[ \t]*desc[ \t]*:*[ \t]*(.*)$", lineread.strip(), re.I)
                        if (regobj):
                            desc = regobj.group(1)
                except:
                    pass
                if (title and desc):
                    memobj = gtk.RadioButton(memobj, title + " (" + desc + ")")
                    try:
                        fileobj = open(self.bootdir + "/" + bootitem, "r")
                        filestr = fileobj.read()
                        fileobj.close()
                        filemd5 = md5.md5(filestr).hexdigest()
                        if (filemd5 == confmd5):
                            memobj.set_active(True)
                    except:
                        pass
                    self.conflist.append([memobj, bootitem])
                    table.attach(memobj, 1, 2, rownumb, rownumb + 1, gtk.FILL, gtk.SHRINK)
                    rownumb += 1
        if (rownumb == oldrow):
            rownumb += 1

        label = gtk.Label(_(" "))
        label.set_line_wrap(False)
        label.set_alignment(0.0, 0.0)
        table.attach(label, 0, 3, rownumb, rownumb + 1, gtk.FILL, gtk.EXPAND)

        self.vbox.pack_start(table, True)

        try:
            hostleng = len(self.hostpref)
            fileobjc = open(self.hostfile, "r")

            for lineread in fileobjc.readlines():
                if (lineread[:hostleng] == self.hostpref):
                    lineread = lineread.strip()
                    self.hostname.set_text(lineread[hostleng:])

            fileobjc.close()

        except:
            pass

    def focus(self):
        self.hostname.grab_focus()

    def initializeUI(self):
        pass

