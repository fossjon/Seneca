Name:		livemedia-modifier
Version:	1.3
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
* Mon Jan 14 2013 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.3-1
- Added a check for root user execution and placed script in the sbin dir

* Fri Jan 11 2013 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.2-1
- Fixed some bugs in detecting the fstab boot partition line

* Thu Jan 10 2013 Jon Chiappetta <jonc_mailbox@yahoo.ca> - 1.1-1
- Initial packaging and release

