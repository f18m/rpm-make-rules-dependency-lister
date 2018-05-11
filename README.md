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

```
rpm_make_rules_dependency_lister --input /my/rpm/folder/myrpm.rpm
```

