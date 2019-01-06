# rpm-make-rules-dependency-lister

[![PyPI version](https://badge.fury.io/py/rpm-make-rules-dependency-lister.svg)](https://badge.fury.io/py/rpm-make-rules-dependency-lister)

This is a tool to allow incremental RPM packaging, which is useful to speed up your testing
if you have many RPM packages and in your development cycle you often need to have just a few
of those RPMs actually re-packaged.

In practice this tool is a simple Python3 script that reads an .rpm file and writes an output text file 
that, if included inside a Makefile, will instruct GNU make about the dependencies 
of the .rpm package, so that such RPM can be rebuilt only when one of the dependencies is updated 
(rather than unconditionally) thus speeding up the time required by packaging.

This tool is agnostic to the RPM contents, to the programming language(s) used in your project,
and to the build system you used to generate binaries, etc.
The format of the output file generated is compatible with GNU make syntax though.

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

## How it works

By default the "rpm-make-rules-dependency-lister" utility will create the association

```
         RPM <-> dependency files
```

by querying the RPM for the list of checksums (typically MD5 or SHA256 sums) and then trying to match
all the files recursively found in the list of directories specified with --search option using 2 criteria:

1) the name of the file
2) its MD5 or SHA256 checksum

The flag --match-executable-by-name-only alters this behavior, for executable files only,
so that only the first criteria (filename) will be used.
Indeed the rpmbuild utility ships by default with a number of post-install scripts executed on the
packaged files. Some of these scripts will alter the packaged files and may change the SHA256 checksum
used internally by rpm-make-rules-dependency-lister to build the association map 
"packaged file <-> filesystem dependency".
An example is the use of the

```
         %debug_package
```

RPM macro. In such cases you can use the --match-executable-by-name-only flag or remove these RPM macros.
A way to get rid of all post-install modification of ELF files is to add:

```
%global __os_install_post %{nil}
```

to your SPEC file.


## How to add to your GNU make Makefile

This utility can be chained in your GNU make process by adding just 3 lines to your Makefile:

```
DEP_FILES := $(foreach spec, $(wildcard *.spec), deps/$(spec).d)        # first line to add

%-$(RPM_VERSION)-$(RPM_RELEASE).$(RPM_ARCH).rpm: %.spec
	... your rpmbuild call...
	rpm_make_rules_dependency_lister --input $@  --output=deps/$<.d --search=<SRCDIR>    # second line to add
```

Where the "SRCDIR" is the directory where you built files to package, that get copied inside the RPM build root.
Finally, at the end of your Makefile add:

```
-include $(DEP_FILES)                               # third line to add
```

That's it!

