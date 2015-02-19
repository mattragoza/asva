Actigraphy Sleep Variable Analysis / ASVA
Version 6.0.4 | Copyright 2015 Matt Ragoza
Developed for the Cameron Lab at the University of Pittsburgh

-------------------------------------------------------------------

Files:

 - asva.py is the main source code and executable
 - asva-gui.py is an under-development GUI using Tkinter
 - awc-dst.py is a batch preprocessor for handling DST changes
	in the middle of .awc files
 - astralmod.py is a modified version of astral.py from the
	astral package, used to calculate sunrise and sunset
 - actigram.py is a utility for graphically visualizing an
	.awc file at the command line

Program requirements:

 - Python 2.7 (Python 3.4 support is in progress)
 - pytz package (required by astralmod.py)
 - Tkinter package (required by asva-gui.py)

Usage:

 - Double click asva.py to run the executable command line interface
 - Call asva.py from the command line through python:
	python asva.py
	
 - Redirect standard input from a .asva file to automate commands:
	python asva.py < abc.asva

 - .asva files are batch jobs for automating commands, view and edit
	them with any standard text editor