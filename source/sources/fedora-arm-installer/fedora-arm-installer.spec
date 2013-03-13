Name:           fedora-arm-installer
Version:        1.0.3
Release:        7%{?dist}
Summary:        Writes binary image files to any specified block device

Group:          Applications/System
License:        GPLv2+
Url:            http://fedoraproject.org/wiki/Fedora_ARM_Installer
Source0:        http://fossjon.fedorapeople.org/packages/fedora-arm-installer/%{name}-%{version}.tar.gz
Source1:        %{name}.pam
Source2:        %{name}.cfg
Source3:        %{name}-helper
Source4:        %{name}.desktop

BuildRequires:  desktop-file-utils
Requires:       PyQt4
Requires:       usermode

BuildArch:      noarch


%description
Allows one to first select a source image (local or remote). The image must be
a binary file containing: [MBR + Partitions + File Systems + Data]. A 
destination block device should then be selected for final installation.


%prep
%setup -q


%build
echo "skipping..."


%install
install -d ${RPM_BUILD_ROOT}%{_sysconfdir}/pam.d
install -pm 0644 %{SOURCE1} ${RPM_BUILD_ROOT}%{_sysconfdir}/pam.d/%{name}

install -d ${RPM_BUILD_ROOT}%{_sysconfdir}/security/console.apps
install -pm 0644 %{SOURCE2} ${RPM_BUILD_ROOT}%{_sysconfdir}/security/console.apps/%{name}

install -d ${RPM_BUILD_ROOT}%{_datadir}/applications
desktop-file-install --dir=${RPM_BUILD_ROOT}%{_datadir}/applications/ %{SOURCE4}

install -d ${RPM_BUILD_ROOT}%{_datadir}/%{name}/data
install -pm 0644 data/* ${RPM_BUILD_ROOT}%{_datadir}/%{name}/data/

install -d ${RPM_BUILD_ROOT}%{_bindir}
ln -s consolehelper ${RPM_BUILD_ROOT}%{_bindir}/%{name}

install -d ${RPM_BUILD_ROOT}%{_sbindir}
install -pm 0755 %{SOURCE3} ${RPM_BUILD_ROOT}%{_sbindir}/
install -pm 0755 %{name} ${RPM_BUILD_ROOT}%{_sbindir}/


%files
%doc docs/LICENSE

%{_sysconfdir}/pam.d/%{name}
%{_sysconfdir}/security/console.apps/%{name}

%{_datadir}/applications/%{name}.desktop
%{_datadir}/%{name}/

%{_bindir}/%{name}

%{_sbindir}/%{name}-helper
%{_sbindir}/%{name}


%changelog
* Wed Mar 13 2013 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.0.3-7
- Sent the choose source dialog return string through a conversion method

* Wed Feb 13 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.2-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Mon Jan 14 2013 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.0.2-5
- Minor tweaks to the specfile files section and license info

* Tue Dec 11 2012 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.0.2-4
- Cleaned up the spec file script creation with the use of Source files

* Thu Aug 30 2012 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.0.2-3
- Modified the way downloads & saves work

* Thu Aug 16 2012 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.0.0-3
- Added a comment regarding dd.exe output format and changed the default archive
  & compression to assume .zip format

* Thu Mar 08 2012 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.0.0-2
- usr share data dir change + desktop file + pipe object cleanup + windows drive
  letters

* Mon Feb 27 2012 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.0.0-1
- Initial packaging
