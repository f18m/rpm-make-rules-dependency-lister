#
# Makefile to build example RPMs and to generate dependency lists using this Python project!
# See main README.md or type "make help" to get more info.
#


#
# VARIABLES
#

RPM_VERSION=1.2.3
RPM_RELEASE=mybuild
RPM_ARCH=x86_64
ALL_TARGET_RPMS := $(foreach spec, $(wildcard *.spec), $(subst .spec,-$(RPM_VERSION)-$(RPM_RELEASE).$(RPM_ARCH).rpm,$(spec)))
DEP_FILES := $(ALL_TARGET_RPMS:%.rpm=%.d)
THIS_DIRECTORY := $(shell readlink -f .)

$(info Target RPMs are: $(ALL_TARGET_RPMS))
$(info Dependency files are: $(DEP_FILES))



#
# TARGETS
#

.PHONY: all dummy_pkg_contents touch_files_pkgA touch_files_pkgB test_file_not_found test_multi_search_dirs clean distclean help

all: dummy_pkg_contents $(ALL_TARGET_RPMS) help

dummy_pkg_contents:
	cd dummy-pkg-contents && make

%-$(RPM_VERSION)-$(RPM_RELEASE).$(RPM_ARCH).rpm: %.spec
	@echo "-----------------------------------------------------------------"
	@echo "--- (Re)Building RPM from spec file $<"
	@echo "-----------------------------------------------------------------"
	rpmbuild --clean --quiet \
		--define='rpm_version $(RPM_VERSION)' \
		--define='rpm_release $(RPM_RELEASE)' \
		--define='topdir $(THIS_DIRECTORY)' \
		-bb $<
	@mv $$HOME/rpmbuild/RPMS/$(RPM_ARCH)/$@ .
	@echo "-----------------------------------------------------------------"
	@echo "--- Generating RPM dependency list for spec file $<"
	@echo "-----------------------------------------------------------------"
	rpm_make_rules_dependency_lister -v --strict --input $@ --explicit-dependencies=$<

touch_files_pkgA:
	# this will force repackaging of pkgA if dependency files have been generated!
	touch dummy-pkg-contents/subdir1/subdir2/test1.txt

touch_files_pkgB:
	# this will force repackaging of pkgB if dependency files have been generated!
	touch dummy-pkg-contents/test-wildcard1.txt

touch_spec_pkgB:
	# this will force repackaging of pkgB if dependency files have been generated!
	touch pkgB.spec
	
test_file_not_found: pkgA-1.2.3-mybuild.x86_64.rpm
	# force searching in a dummy folder so that we can test how the utility behaves
	mkdir -p /tmp/dummy1 /tmp/dummy2 /tmp/dummy3
	rpm_make_rules_dependency_lister -v --strict --input pkgA-1.2.3-mybuild.x86_64.rpm --search=/tmp/dummy1,/tmp/dummy2,/tmp/dummy3 --dump-missed-files=missed-files

test_multi_search_dirs: pkgA-1.2.3-mybuild.x86_64.rpm
	# search 2 dirs: they should contain all files packaged in pkgA
	rpm_make_rules_dependency_lister -v --strict --input pkgA-1.2.3-mybuild.x86_64.rpm --search=$(THIS_DIRECTORY)/dummy-pkg-contents/subdir1,$(THIS_DIRECTORY)/dummy-pkg-contents/subdir3

test_packaged_file_removed:
	rm -f dummy-pkg-contents/test-wildcard2.txt
	@echo "Now relaunch 'make', it should not fail but trigger regen of RPM B"

clean:
	rm -f *.rpm
	rm -f missed-files

distclean: clean
	rm -f *.d

help:
	@echo
	@echo "-----------------------------------------------------------------"
	@echo "--- rpm-make-rules-dependency-lister TESTS HELP"
	@echo "-----------------------------------------------------------------"
	@echo "To understand the purpose of this small Python utility just type"
	@echo "   make"
	@echo "a couple of times: the first one you will see both RPM A and RPM B"
	@echo "rebuilt and repackaged. The second time the dependency files generated"
	@echo "on the first run will instruct GNU make that no repackaging is needed."
	@echo
	@echo "After that you can play with some tests:"
	@echo "  make touch_files_pkgA    or    make touch_files_pkgB"
	@echo "and then:"
	@echo "  make"
	@echo "too see what gets rebuilt. Or:"
	@echo "  make test_multi_search_dirs"
	@echo "  ..."
	@echo

# 
# This is the key point of the incremental RPM building process:
# automatically-generated RPM dependency list is included in this makefile to instruct
# GNU make about the conditions for re-building the RPM
#
-include $(DEP_FILES)
