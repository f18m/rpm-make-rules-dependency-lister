# Example SPEC

Name: pkgB
Summary: Example package
Group: Applications/Internet
Version: %{rpm_version}
Release: %{rpm_release}
License: GPL
Vendor: None

Requires: systemPkgB

%description
Metapackage for example purposes

%install
rm -rf %{buildroot}/test-install
mkdir -p %{buildroot}/test-install
cp dummy-pkg-contents/test3.txt						%{buildroot}/test-install

%clean
%pre
%post
%posttrans
%preun
%postun
%files
/test-install/*.txt
