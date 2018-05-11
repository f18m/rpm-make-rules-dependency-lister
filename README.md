# rpm-make-rules-dependency-lister

This is a simple Python3 script that reads an .rpm file and writes an output text file 
that, if included inside a Makefile, will instruct GNU make about the dependencies 
of the .rpm, so that such RPM can be rebuilt only when one of the dependencies is updated 
(rather than unconditionally) thus speeding up the time required by "make".

## How to install

```
pip3 install rpm-make-rules-dependency-lister
```

## How to use

The following command
```
rpm_make_rules_dependency_lister -v --input /my/rpm/folder/myrpm.rpm
```
generates a file '/my/rpm/folder/myrpm.d' that you can inspect to understand what this utility does
with your RPM file.

## Explanation

The 'tests' directory is used to test and showcase this utility. Get it with:

```
pip3 install rpm-make-rules-dependency-lister   # install the utility to be able to run tests
git clone https://github.com/f18m/rpm-make-rules-dependency-lister.git
cd rpm-make-rules-dependency-lister/tests
ls -l
```

You can notice that the directory contains just 2 spec files after a clean checkout from GIT.
Now if you run:

```
make                     # all RPMs are rebuilt (first time build)
ls -l
```

you will build RPMs from those spec files (you need "rpmbuild" utility installed!) and, together
with them, dependency files (those *.d files). The dependency files are generated using this
"rpm-make-rules-dependency-lister" utility. More on that later.
Now if you run:

```
make                     # nothing gets rebuilt
```

again you will notice that nothing gets rebuilt. This is because GNU make now has the list of 
packaged files and will not unnecessarily rebuild the RPMs unless the packaged files are updated.
You can test it by running:

```
make touch_files_pkgA    # this alters the mtime of files packaged from RPM A
make                     # now the RPM A is rebuilt!
```

Now if your project builds several RPMs, this utility can greatly reduce the time it takes to
regenerate them!

## How to add to your Makefile

This utility can be chained in your GNU make process by adding just 3 lines to your Makefile:

```
DEP_FILES := $($(wildcard *.spec):%.spec=%.d)        # first line to add

%-$(RPM_VERSION)-$(RPM_RELEASE).$(RPM_ARCH).rpm: %.spec
	... your rpmbuild call...
	rpm_make_rules_dependency_lister --input $@      # second line to add
```

Then at the end of your Makefile:

```
-include $(DEP_FILES)                               # third line to add
```
