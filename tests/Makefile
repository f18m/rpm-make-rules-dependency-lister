#
# Makefile to build example RPMs
#
RPM_VERSION=1.2.3
RPM_RELEASE=mybuild
ALL_TARGET_RPMS := $(foreach spec, $(wildcard *.spec), $(subst .spec,-$(RPM_VERSION)-$(RPM_RELEASE).x86_64.rpm,$(spec)))
DEP_FILES := $(ALL_TARGET_RPMS:%.rpm=%.d)

$(info Target RPMs are: $(ALL_TARGET_RPMS))
$(info Dependency files are: $(DEP_FILES))

all: $(ALL_TARGET_RPMS)

%-$(RPM_VERSION)-$(RPM_RELEASE).x86_64.rpm: %.spec
	rpmbuild --clean --build-in-place \
		--define='rpm_version $(RPM_VERSION)' \
		--define='rpm_release $(RPM_RELEASE)' \
		-bb $<
	mv $$HOME/rpmbuild/RPMS/x86_64/$@ .
	rpm_make_rules_dependency_lister --rpm $@ --outfile $(@:%.rpm=%.d)

touch_files_pkgA:
	touch dummy-pkg-contents/subdir1/subdir2/test1.txt

touch_files_pkgB:
	touch dummy-pkg-contents/test3.txt

clean:
	rm -f *.rpm
	
-include $(DEP_FILES)
