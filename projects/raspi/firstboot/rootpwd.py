import gtk
import libuser
import os, string, sys, time
import os.path
import pwd
import unicodedata
import re
import shutil
import subprocess

from firstboot.config import *
from firstboot.constants import *
from firstboot.functions import *
from firstboot.module import *
from firstboot.pwcheck import Password
from firstboot.pwcheck import StrengthMeterWithLabel

import gettext
_ = lambda x: gettext.ldgettext("firstboot", x)
N_ = lambda x: x

class moduleClass(Module):
    def __init__(self):
        Module.__init__(self)
        self.priority = 102
        self.sidebarTitle = _("Root User")
        self.title = _("Root User Settings")
        self.icon = "smolt.png"
        
        self.admin = libuser.admin()

    def apply(self, interface, testing=False):
        username = "root"
        password = self.passwordEntry.get_text()
        confirm = self.confirmEntry.get_text()
        
        if not password or not confirm:
            self._showErrorMessage(_("You must enter and confirm a password for root."))
            return RESULT_FAILURE
        
        if password != confirm:
            self._showErrorMessage(_("The passwords do not match. Please enter the password again."))
            return RESULT_FAILURE
        
        user = self.admin.lookupUserByName(username)
        
        if not user:
            self._showErrorMessage(_("The root user has not been created yet."))
            return RESULT_FAILURE
        
        self.admin.setpassUser(user, password, 0)
        
        return RESULT_SUCCESS

    def createScreen(self):
        self.vbox = gtk.VBox(spacing=4)
        
        table = gtk.Table(4, 4)
        table.set_row_spacings(4)
        table.set_col_spacings(4)
        
        label = gtk.Label(_("You must configure the root user account (Administrator)"))
        table.attach(label, 0, 2, 0, 1, gtk.FILL)
        
        label = gtk.Label(_("Password:"))
        label.set_use_underline(True)
        label.set_alignment(0.0, 0.5)
        #label.set_mnemonic_widget(self.passwordEntry)
        self.passwordEntry = gtk.Entry()
        self.passwordEntry.set_visibility(False)
        self.strengthLabel = StrengthMeterWithLabel()
        
        table.attach(label, 0, 1, 1, 2, gtk.FILL)
        table.attach(self.passwordEntry, 1, 2, 1, 2, gtk.SHRINK, gtk.FILL, 5)
        table.attach(self.strengthLabel, 2, 3, 1, 2, gtk.FILL)
        
        label = gtk.Label(_("Confirm Password:"))
        label.set_use_underline(True)
        label.set_alignment(0.0, 0.5)
        #label.set_mnemonic_widget(self.confirmEntry)
        self.confirmEntry = gtk.Entry()
        self.confirmEntry.set_visibility(False)
        self.confirmIcon = gtk.Image()
        self.confirmIcon.set_alignment(0.0, 0.5)
        self.confirmIcon.set_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
        self.confirmIcon.set_no_show_all(True)
        
        table.attach(label, 0, 1, 2, 3, gtk.FILL)
        table.attach(self.confirmEntry, 1, 2, 2, 3, gtk.SHRINK, gtk.FILL, 5)
        table.attach(self.confirmIcon, 2, 3, 2, 3, gtk.FILL)
        
        self.passwordEntry.connect("changed", self.passwordEntry_changed, self.strengthLabel, self.confirmEntry, self.confirmIcon)
        self.confirmEntry.connect("changed", self.confirmEntry_changed, self.passwordEntry, self.confirmIcon)
        
        self.vbox.pack_start(table, False)

    def initializeUI(self):
        pass

    def _showErrorMessage(self, text):
        dlg = gtk.MessageDialog(None, 0, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, text)
        dlg.set_position(gtk.WIN_POS_CENTER)
        dlg.set_modal(True)
        rc = dlg.run()
        dlg.destroy()
        return None

    def passwordEntry_changed(self, entry, strengthLabel, confirmEntry, confirmIcon):
        self.confirmEntry_changed(confirmEntry, entry, confirmIcon)

        pw = entry.get_text()
        if not pw:
            strengthLabel.set_text("")
            strengthLabel.set_fraction(0.0)
            return

        pw = Password(pw)
        strengthLabel.set_text('%s' % pw.strength_string)
        strengthLabel.set_fraction(pw.strength_frac)

    def confirmEntry_changed(self, entry, passwordEntry, confirmIcon):
        pw = passwordEntry.get_text()
        if not pw:
            # blank icon
            confirmIcon.hide()
            return

        if pw == entry.get_text():
            confirmIcon.show()
        else:
            # blank icon
            confirmIcon.hide()
