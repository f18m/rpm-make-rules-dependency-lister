dist:
	python3 setup.py sdist
	python3 setup.py bdist_wheel

clean:
	rm -rf build dist *.egg-info

test_install:
	-sudo pip3 uninstall rpm-make-rules-dependency-lister
	sudo pip3 install dist/*.whl
	@echo
	@echo "Running installed utility:"
	@echo
	rpm_make_rules_dependency_lister --help

upload:
	twine upload dist/*

.PHONY: dist clean test_install upload
