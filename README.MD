ASVA | Actigraphy Sleep Variable Analysis
Cameron Lab at the University of Pittsburgh

-------------------------------------------------------------------

Files:

 - asva.py is the main source code and command line script
 - awc-dst.py is a batch preprocessor for handling DST changes
	in the middle of .awc files
 - test folder contains various .awc files for testing

Program requirements:

 - Python 3
 - ephem, a Python package for astronomical calculations

Usage:

 - run from the command line as follows:

 	python asva.py [-t THRESHOLD] [-c CRITERIA] [-o OUTPUT] FILE_PATTERN

 - THRESHOLD is the sensitivity to use for the Cole-Kripke scoring algorithm.
 - CRITERIA is the ratio of minutes to classify transitions between states.
 - OUTPUT is the name of the file to write the results to.
 - FILE_PATTERN is a glob-style pattern to gather input files.
 - Alternatively, input data can be piped in as a list of filepaths from ls.