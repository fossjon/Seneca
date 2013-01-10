Name:		livemedia-modifier
Version:	1.1
Release:	1%{?dist}
Summary:	Takes an ARM image file and finalizes it with device specific configurations and modifications

Group:		Utility
License:	GPLv2+
URL:		
Source0:	

BuildRequires:	
Requires:	

%description


%prep
%setup -q


%build
echo "skipping build..."


%install
rm -rf $RPM_BUILD_ROOT
make install DESTDIR=$RPM_BUILD_ROOT


%files
%doc



%changelog

