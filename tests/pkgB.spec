# Example SPEC

Name: pkgB
Summary: Example package
Group: Applications/Internet
Version: %{rpm_version}
Release: %{rpm_release}
License: GPL
Vendor: None

# Typically here you would have a list of other RPM dependencies:
#Requires: systemPkgB

%description
Metapackage for example purposes

%install
rm -rf %{buildroot}/test-install
mkdir -p %{buildroot}/test-install

# test wildcard in copy: 
cp %{topdir}/dummy-pkg-contents/test-wildcard*					%{buildroot}/test-install
cp %{topdir}/dummy-pkg-contents/testbinary						%{buildroot}/test-install

# test packaging a file that appears multiple times inside the search directories:
cp %{topdir}/dummy-pkg-contents/subdir3/testfile-present-multiple-times.txt 	%{buildroot}/test-install

%clean
%pre
%post
%posttrans
%preun
%postun
%files
/test-install/*.txt
%attr(755,-,-) /test-install/testbinary
