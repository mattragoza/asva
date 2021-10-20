# Actigraphy Sleep Variable Analysis

This program can be used to detect periods of sleep and wakefulness in accelerometer data. It was developed for the Cameron Lab at the University of Pittsburgh, and the default parameters are tuned for use in non-human primates.

## Requirements

 - Python 3
 - Python packages `ephem` and `pytz`

## Usage

Run from the command line as follows:
```
python asva.py [-t THRESHOLD] [-c CRITERIA] [-o OUTPUT] FILE_PATTERN
```

- THRESHOLD is the sensitivity to use for the sleep scoring algorithm (default=1.0).
- CRITERIA is the ratio of minutes for classifying transitions between states (default=9/10).
  - i.e. 9/10 indicates that 9 sleep minutes in a 10 minute window determine the onset of a sleep period.
- OUTPUT is the name of a file for writing out the results.
- FILE_PATTERN is a glob-style pattern of input files.
