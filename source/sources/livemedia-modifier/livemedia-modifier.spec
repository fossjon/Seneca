Name:		livemedia-modifier
Version:	1.8
Release:	1%{?dist}
Summary:	Takes an ARM image file and finalizes it with device specific configurations and modifications

Group:		Utility
License:	GPLv2+
URL:		http://fossjon.fedorapeople.org/source/fedora/livemedia-modifier/%{name}
Source0:	%{name}

#BuildRequires:	python
Requires:	python
BuildArch:	noarch


%description
Performs some last minute customizations of ARM-based image files
so that they are tailored for their specific device types. 

%prep
echo "skipping prep..."


%build
echo "skipping build..."


%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/%{_sbindir}
install -m 0755 %{SOURCE0} $RPM_BUILD_ROOT/%{_sbindir}/


%files
%{_sbindir}/%{name}


%changelog
* Wed Feb 06 2013 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.8-1
- Changed the partition label and fstab line mod for guru

* Mon Feb 04 2013 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.7-1
- Added a small sleep/loop after creating the loopback and before mounting it

* Fri Feb 01 2013 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.6-1
- Removed vexpress boot script creation and modified guru fstab configuration

* Thu Jan 24 2013 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.5-1
- Removed some code for the creation of guru images

* Wed Jan 23 2013 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.4-1
- Fixed a small bug in creating a rootfs in lmm

* Mon Jan 14 2013 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.3-1
- Added a check for root user execution and placed script in the sbin dir

* Fri Jan 11 2013 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.2-1
- Fixed some bugs in detecting the fstab boot partition line

* Thu Jan 10 2013 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.1-1
- Initial packaging and release

