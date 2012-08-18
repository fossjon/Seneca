Name:		styrene
Version:	0.1
Release:	1%{?dist}
Summary:	Database-driven package development.

Group:		Utilities
License:	GPLv2+
Source0:	styrene-%{version}.tar.gz
BuildRoot:	%(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)

BuildRequires: python2-devel

%description
Allows one to load and mark a database with primary arch packages.
Capable of sending builds to a koji build system.
Visual web component for manual package building.

%prep
%setup -q

%install
mkdir -p $RPM_BUILD_ROOT%{python_sitelib}
cp -frv ./styrene-lib/styrene $RPM_BUILD_ROOT%{python_sitelib}/

mkdir -p $RPM_BUILD_ROOT%{_bindir}
cp -fv ./styrene $RPM_BUILD_ROOT%{_bindir}/

%clean
rm -rf $RPM_BUILD_ROOT

%files
%{python_sitelib}/styrene
%{_bindir}/styrene

%changelog
* Mon Jul 4 2010 Jon Chiappetta <jonc_mailbox@yahoo.ca> 0.1
- init release
