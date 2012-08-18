import gtk

from firstboot.config import *
from firstboot.constants import *
from firstboot.functions import *
from firstboot.module import *

import gettext
_ = lambda x: gettext.ldgettext("firstboot", x)
N_ = lambda x: x

class moduleClass(Module):
    def __init__(self):
        Module.__init__(self)
        self.priority = 101
        self.sidebarTitle = N_("Filesystem")
        self.title = N_("Filesystem Settings")
        self.icon = "workstation.png"

    def apply(self, interface, testing=False):
        sizeflag = self.checkbox.get_active()
        swapsize = int(self.scale.get_value())

        if (sizeflag):
            try:
                fileobjc = open("/.rootfs-repartition", "w")
                fileobjc.write("true" + "\n")
                fileobjc.close()

            except:
                return RESULT_FAILURE

            try:
                fileobjc = open("/.swapsize", "w")
                fileobjc.write(str(swapsize) + "\n")
                fileobjc.close()

            except:
                return RESULT_FAILURE

        else:
            try:
                os.unlink("/.rootfs-repartition")

            except:
                pass

            try:
                os.unlink("/.swapsize")

            except:
                pass

        return RESULT_SUCCESS

    def createScreen(self):
        self.vbox = gtk.VBox(spacing=10)

        table = gtk.Table(8, 1)
        table.set_row_spacings(4)
        table.set_col_spacings(4)

        label = gtk.Label(_("Since we ship a condensed Raspberry Pi image, you may be able to get more space by selecting to resize the filesystem below. The actual resize will take place upon next reboot. If unsure, just leave the default values selected below."))
        label.set_line_wrap(True)
        label.set_alignment(0.0, 0.0)
        label.set_size_request(500, -1)
        table.attach(label, 0, 1, 0, 1, gtk.FILL)

        label = gtk.Label(_(" "))
        table.attach(label, 0, 1, 1, 2, gtk.FILL)

        self.checkbox = gtk.CheckButton(label="Resize Root Filesystem?", use_underline=False)
        table.attach(self.checkbox, 0, 1, 2, 3, gtk.FILL)

        label = gtk.Label(_(" "))
        table.attach(label, 0, 1, 3, 4, gtk.FILL)

        self.swaptext = gtk.Label(_("Swap File Size Selection (in Megabytes [MB]). (Hint: Set the swap size to \"0\" if you just want to resize the root partition)."))
        self.swaptext.set_line_wrap(True)
        self.swaptext.set_alignment(0.0, 0.0)
        self.swaptext.set_size_request(500, -1)
        self.swaptext.set_sensitive(False)
        table.attach(self.swaptext, 0, 1, 4, 5, gtk.FILL)

        adjust = gtk.Adjustment(0, 0, 2048, 256, 0, 0)
        self.scale = gtk.HScale(adjust)
        self.scale.set_digits(0)
        self.scale.set_size_request(500, -1)
        self.scale.set_sensitive(False)
        self.scale.grab_focus()
        table.attach(self.scale, 0, 1, 5, 6, gtk.FILL)

        self.vbox.pack_start(table, False)

        self.scale.set_value(512)
        self.showvalue = int(self.scale.get_value())
        self.realvalue = self.showvalue

        self.checkbox.connect("clicked", self.boxclicked)
        self.scale.connect("value-changed", self.scalemoved)

        self.checkbox.set_active(True)
        self.boxclicked(None)

    def focus(self):
        self.scale.grab_focus()

    def initializeUI(self):
        pass

    def boxclicked(self, event):
        if (self.checkbox.get_active()):
            self.swaptext.set_sensitive(True)
            self.scale.set_sensitive(True)

        else:
            self.swaptext.set_sensitive(False)
            self.scale.set_sensitive(False)

            self.scale.set_value(512)
            self.showvalue = int(self.scale.get_value())
            self.realvalue = self.showvalue

    def scalemoved(self, event):
        presvalue = int(self.scale.get_value())
        evenvalue = 16
        movevalue = (evenvalue / 2)

        self.realvalue += (presvalue - self.showvalue)

        if (abs(self.realvalue - self.showvalue) >= movevalue):
            modsvalue = (presvalue % evenvalue)
            modavalue = ((evenvalue - modsvalue) % evenvalue)

            if ((self.realvalue - self.showvalue) > 0):
                self.showvalue = (presvalue + modavalue)

            if ((self.realvalue - self.showvalue) < 0):
                self.showvalue = (presvalue - modsvalue)

            self.realvalue = self.showvalue

        self.scale.set_value(self.showvalue)

