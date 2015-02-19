
#!/usr/bin/python

import sys
import os
import time

SEP = "\t|"
UNIT = "x"
RATE = 25
SCALE = 10
WIDTH = 80
COLUMN = 10
GRAPH = WIDTH-COLUMN

if len(sys.argv) != 2: quit()
inputFile = open(sys.argv[1], 'r')

content = inputFile.readlines()
header = content[:11]
data = content[11:]

for line in header: print line,

for line in data:

	try:

		activity = int(line.replace("M\n", ""))

		numUnits = int((activity+SCALE/2)/float(SCALE))
		if numUnits>GRAPH: numUnits = GRAPH
		print str(activity) + SEP + UNIT*numUnits

		if RATE: time.sleep(1/float(RATE))

	except KeyboardInterrupt:

		try: raw_input("\t\t\t\t--paused--")
		except KeyboardInterrupt:
			quit()


