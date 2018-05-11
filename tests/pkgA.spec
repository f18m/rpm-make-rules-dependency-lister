# Example SPEC

Name: pkgA
Summary: Example package
Group: Applications/Internet
Version: %{rpm_version}
Release: %{rpm_release}
License: GPL
Vendor: None

Requires: systemPkgA, pkgB

%description
Metapackage for example purposes

%install
rm -rf %{buildroot}/test-install
mkdir -p %{buildroot}/test-install
cp %{topdir}/dummy-pkg-contents/subdir1/subdir2/test1.txt		%{buildroot}/test-install
cp %{topdir}/dummy-pkg-contents/subdir1/test2.txt				%{buildroot}/test-install

%clean
%pre
%post
%posttrans
%preun
%postun
%files
/test-install/*.txt
