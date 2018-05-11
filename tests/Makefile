#
# Makefile to build example RPMs and to generate dependency lists using this Python project!
# See main README.md
#
RPM_VERSION=1.2.3
RPM_RELEASE=mybuild
RPM_ARCH=x86_64
ALL_TARGET_RPMS := $(foreach spec, $(wildcard *.spec), $(subst .spec,-$(RPM_VERSION)-$(RPM_RELEASE).$(RPM_ARCH).rpm,$(spec)))
DEP_FILES := $(ALL_TARGET_RPMS:%.rpm=%.d)
THIS_DIRECTORY := $(shell readlink -f .)

$(info Target RPMs are: $(ALL_TARGET_RPMS))
$(info Dependency files are: $(DEP_FILES))

all: $(ALL_TARGET_RPMS)

%-$(RPM_VERSION)-$(RPM_RELEASE).$(RPM_ARCH).rpm: %.spec
	@echo "--- Building RPM from spec file $<"
	rpmbuild --clean \
		--define='rpm_version $(RPM_VERSION)' \
		--define='rpm_release $(RPM_RELEASE)' \
		--define='topdir $(THIS_DIRECTORY)' \
		-bb $<
	@mv $$HOME/rpmbuild/RPMS/$(RPM_ARCH)/$@ .
	@echo "--- Generating RPM dependency list"
	rpm_make_rules_dependency_lister -v --strict --input $@

touch_files_pkgA:
	touch dummy-pkg-contents/subdir1/subdir2/test1.txt

touch_files_pkgB:
	touch dummy-pkg-contents/test3.txt

clean:
	rm -f *.rpm

distclean: clean
	rm -f *.d

# 
# This is the key point of the program:
# automatically-generated RPM dependency list is included in this makefile to instruct
# GNU make about the conditions for re-building the RPM
#
-include $(DEP_FILES)
