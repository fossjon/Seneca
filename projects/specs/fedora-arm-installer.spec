Name:		fedora-arm-installer
Version:	1.0.0
Release:	3%{?dist}
Summary:	Writes binary image files to any specified block device

Group:		Applications/System
License:	GPLv2+
URL:		http://fedoraproject.org/wiki/Fedora_ARM_Installer
Source0:	http://fossjon.fedorapeople.org/%{name}-%{version}.tar.gz

BuildArch:	noarch
BuildRequires:	desktop-file-utils
Requires:	python2
Requires:	PyQt4
Requires:	usermode

%description
Allows one to first select a source image (local or remote). The image must be
a binary file containing: [MBR + Partitions + File Systems + Data]. A 
destination block device should then be selected for final installation.

%prep
%setup -q

%build
mkdir pam
cat > pam/%{name} <<EOF
#%PAM-1.0
auth		include		config-util
account		include		config-util
session		include		config-util
EOF

mkdir cfg
cat > cfg/%{name} <<EOF
PROGRAM=%{_sbindir}/%{name}-helper
SESSION=true
EOF

mkdir exe
cat > exe/%{name}-helper <<EOF
#!/bin/bash
export DBUS_SESSION_BUS_ADDRESS=needed
export DESKTOP_SESSION=needed
export GNOME_DESKTOP_SESSION_ID=needed
exec %{_sbindir}/%{name}
EOF

mkdir dsk
cat > dsk/%{name}.desktop <<EOF
[Desktop Entry]
Encoding=UTF-8
Name=Fedora ARM Image Installer
Comment=Install a Fedora ARM or Fedora Remix ARM image to an SD card
Exec=fedora-arm-installer
Terminal=false
Type=Application
Icon=/usr/share/%{name}/data/logo.png
StartupNotify=true
X-Desktop-File-Install-Version=0.18
Categories=System
EOF

%install
install -d ${RPM_BUILD_ROOT}%{_sysconfdir}/pam.d
install -pm 0644 pam/* ${RPM_BUILD_ROOT}%{_sysconfdir}/pam.d/

install -d ${RPM_BUILD_ROOT}%{_sysconfdir}/security/console.apps
install -pm 0644 cfg/* ${RPM_BUILD_ROOT}%{_sysconfdir}/security/console.apps/

install -d ${RPM_BUILD_ROOT}%{_datadir}/applications
desktop-file-install --dir=${RPM_BUILD_ROOT}%{_datadir}/applications/ dsk/*

install -d ${RPM_BUILD_ROOT}%{_datadir}/%{name}/data
install -pm 0644 data/* ${RPM_BUILD_ROOT}%{_datadir}/%{name}/data/

install -d ${RPM_BUILD_ROOT}%{_bindir}
ln -s consolehelper ${RPM_BUILD_ROOT}%{_bindir}/%{name}

install -d ${RPM_BUILD_ROOT}%{_sbindir}
install -pm 0755 exe/* ${RPM_BUILD_ROOT}%{_sbindir}/
install -pm 0755 %{name} ${RPM_BUILD_ROOT}%{_sbindir}/

%files
%doc docs/LICENSE

%{_sysconfdir}/pam.d/%{name}
%{_sysconfdir}/security/console.apps/%{name}

%{_datadir}/applications/%{name}.desktop
%{_datadir}/%{name}/data/

%{_bindir}/%{name}

%{_sbindir}/%{name}-helper
%{_sbindir}/%{name}

%changelog
* Thu Aug 16 2012 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.0.0-3
- Added a comment regarding dd.exe output format and changed the default archive
  + compression to assume .zip format

* Thu Mar 08 2012 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.0.0-2
- usr share data dir change + desktop file + pipe object cleanup + windows drive
  letters

* Mon Feb 27 2012 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.0.0-1
- Initial packaging
