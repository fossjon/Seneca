Name:           moji-client
Version:        0.2
Release:        1%{?dist}
Summary:        Mini client-side build script (for armv5tel F15 bringup)

License:        GPLv2+
Source0:        %{name}-%{version}.tgz

#BuildRequires:  
Requires:       mock
Requires:	coreutils
Requires(pre):  shadow-utils

BuildArch:	noarch

%description
Moji is a mini client-server buildsystem originally created for the armv5tel
Fedora 15 bringup effort. This package contains the client side script
configured for use with that effort.

%prep
%setup -q


%build
echo "Nothing to do (for 'build')."


%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/%{_bindir} %{buildroot}/%{_sysconfdir}/mock %{buildroot}/%{_initrddir}
install -p moji %{buildroot}/%{_bindir}
install -p moji-client.sh %{buildroot}/%{_bindir}
install -p moji-client %{buildroot}/%{_initrddir}
install -p *.cfg %{buildroot}/%{_sysconfdir}/mock/


%files
%defattr (-,root,root,-)
%{_bindir}/*
%{_initrddir}/*
%{_sysconfdir}/mock/*
%doc COPYING



%pre
getent group moji >/dev/null || groupadd -r moji
getent passwd moji >/dev/null || \
    useradd -r -d %{_datadir}/%{name} \
    -g moji -s /bin/bash \
    -c "moji build client" moji
install -d -m 0755 -o moji -g moji %{_datadir}/%{name}
usermod -aG mock moji
exit 0


%changelog
* Thu Oct 13 2011 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 0.2-1
- Updated to 0.2

* Wed Oct 12 2011 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 0.1-15
- better child proc handlling

* Tue Oct 11 2011 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 0.1-14
- Fixed logfile location

* Tue Oct 11 2011 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 0.1-13
- Fixed typo in %pre

* Tue Oct 11 2011 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 0.1-12
- Created user directory

* Tue Oct 11 2011 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 0.1-11
- Minor script update

* Fri Oct 07 2011 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 0.1-10
- Minor script update

* Thu Oct 06 2011 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 0.1-9
- Fix up repo config

* Thu Oct 06 2011 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 0.1-8
- Add moji user to mock group

* Thu Oct 06 2011 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 0.1-7
- Run script as non-root user

* Thu Oct 06 2011 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 0.1-6
- Permission fix

* Thu Oct 06 2011 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 0.1-5
- Minor script change

* Thu Oct 06 2011 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 0.1-4
- Fixed typo in summary line

* Fri Oct 06 2011 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 0.1-3
- Fixes to service script: binary name, redirect to log file

* Fri Oct 06 2011 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 0.1-2
- Revised service script to fix binary name

* Wed Oct 04 2011 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 0.1-1
- Initial packaging
