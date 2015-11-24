#ASVA | Actigraphy Sleep Variable Analysis

###Cameron Lab at the University of Pittsburgh

-------------------------------------------------------------------

##Requirements

 - Python 3
 - Python packages ephem and pytz

##Usage

 - run from the command line as follows:

 	python asva.py [-t THRESHOLD] [-c CRITERIA] [-o OUTPUT] FILE_PATTERN

 - THRESHOLD is the sensitivity to use for the Cole-Kripke scoring algorithm.
 - CRITERIA is the ratio of minutes to classify transitions between states.
 - OUTPUT is the name of the file to write the results to.
 - FILE_PATTERN is a glob-style pattern to gather input files.
 - Alternatively, input data can be piped in as a list of filepaths, and if no output file is specified the results will be sent to stdout.
