Name:		raspi-splash
Version:	1.0
Release:	6%{?dist}
Summary:	Uses OpenGL to display an initial loading splash screen

Group:		Amusements/Graphics
License:	GPLv2+
Source0:	%{name}-%{version}.tgz

BuildRequires:  systemd-units
BuildRequires:	raspberrypi-vc-libs
BuildRequires:	raspberrypi-vc-libs-devel
BuildRequires:	raspberrypi-vc-static
#BuildRequires:	raspberrypi-vc-utils

%global systemdl /lib/systemd/system
%global systemde /etc/systemd/system

%description
Based on the raspberry-pi-vc-demos package, display an initial splash 
loading screen during boot for the user.

%prep
%setup -q

echo "setup"

%build
tar -xzvf zlib-1.2.7.tar.gz
cd zlib-1.2.7
./configure
make
cd ..
make

cat <<EOF > %{name}-helper
#!/bin/bash
%{_bindir}/%{name} %{_datadir}/%{name}/data/logo %{_datadir}/%{name}/data/anim &
EOF

cat <<EOF > %{name}-start.service
[Unit]
Description=Start Rasp Pi Boot Screen
DefaultDependencies=no
Before=systemd-vconsole-setup.service

[Service]
ExecStart=/bin/raspi-splash-helper
Type=forking

[Install]
WantedBy=sysinit.target
EOF

cat <<EOF > %{name}-stop.service
[Unit]
Description=Stop Rasp Pi Boot Screen
DefaultDependencies=no
After=rc-local.service

[Service]
ExecStart=/bin/systemctl stop %{name}-start.service
Type=oneshot

[Install]
WantedBy=multi-user.target
EOF

echo "build"

%install
install -d %{buildroot}/%{_datadir}/%{name}

mv data %{buildroot}/%{_datadir}/%{name}/
mv zlib-1.2.7 %{buildroot}/%{_datadir}/%{name}/

install -d %{buildroot}/%{_bindir}
install -m 755 -p splash.bin %{buildroot}/%{_bindir}/%{name}
install -m 755 -p %{name}-helper %{buildroot}/%{_bindir}/

install -d %{buildroot}/%{systemdl}
install -m 644 -p *.service %{buildroot}/%{systemdl}/

install -d %{buildroot}/%{systemde}/sysinit.target.wants
install -d %{buildroot}/%{systemde}/multi-user.target.wants

ln -s %{systemdl}/%{name}-start.service %{buildroot}/%{systemde}/sysinit.target.wants/
ln -s %{systemdl}/%{name}-stop.service %{buildroot}/%{systemde}/multi-user.target.wants/

echo "install"

%files
%doc
%{_datadir}/*
%{_bindir}/*
%{systemdl}/*
%{systemde}/*

%changelog
* Fri Aug 17 2012 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.0-6
- Converted back to the gif version plus zlib c lib

* Thu Aug 09 2012 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.0-5
- Fixed up the generated systemd service files

* Wed Aug 08 2012 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.0-4
- Simpler version with only one 2d rotating image

* Tue Jul 24 2012 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.0-3
- New logo rendering

* Mon Jul 16 2012 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.0-2
- Initial packaging and release

