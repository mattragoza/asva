The file asva.py is a Python program for scoring actigraphy data.

# Instructions

Open a terminal program such as cmd on Windows or bash on Mac or Linux.
Navigate to the folder where asva.py is located on your computer using the
following command:

```
cd <path_to_directory>
```

Once in this folder, run the actigraphy scoring progam using one of the following commands:
```
python asva.py FILE_PATTERN -o OUTPUT_FILE
python asva.py FILE_PATTERN > OUTPUT_FILE
```
The FILE_PATTERN argument is how you specify what AWC files you want to score. The OUTPUT_FILE argument is the path for the file to write the output values to, in a .csv-like format.

Say you want to score just one file called test.awc which is in the same folder as asva.py, and then write the ouput to test.csv. You can enter:
```
python asva.py test.awc -o test.csv
```
If you have a bunch of AWC files in a folder called "AWC files", which is in the same folder as asva.py, you could instead enter the command as:
```
python asva.py "AWC files\*.awc" -o test.csv
```
Here we are using a wildcard character, which grabs all the files whose path matches a certain pattern- in this case, all the files in the folder "AWC files" that have the .awc file extension.

If a filename for file pattern uses spaces or wildcard characters, it has to be enclosed in quotes to reduce ambiguity. Also note that filenames are case-sensitive in most operating systems.

By default, the program uses 7:00:00 and 19:00:00 as the lights on and off times, and does NOT take into account sunrise or sunset. These parameters can be changed using the -l option to specify different lights on and off times, and/or the -d flag to tell the program to compare them to daylight.

Entering this command would use 8am to 8pm as the light period:
```
python asva.py FILE_PATTERN -o OUTPUT_FILE -l 8:00:00,20:00:00
```
The times must be in 24-hour HH:MM:SS format, and separated by a single comma with no space.

This next command would use 6am to 6pm as the light period, but compare to sunrise and sunset and use those during times of the year when they would define the actual light period (for example, in a facility with skylights):
```
python asva.py FILE_PATTERN -o OUTPUT_FILE -l 6:00:00,18:00:00 -d
```
For questions, contact Matt Ragoza at mtr22 at pitt dot edu.
