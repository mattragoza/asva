# ACTIGRAPHY SLEEP VARIABLE ANALYSIS
# Merged from main_sleep_analysis_v5.py and verify_activity.py
# Copyright 2015 Matt Ragoza
VERSION = "6.2.0"

import sys
import os
import platform
import csv
import glob
import re
import time
import math
import datetime

sys.path.append(os.path.dirname(os.path.realpath(__file__))+"\\import")
from astralmod import Astral
import pytz
sys.path.remove(os.path.dirname(os.path.realpath(__file__))+"\\import")


# Global constants
PROMPT = "(asva) "
SUPPORTED_TYPES = [".awc", ".vl.csv"]
AWC_HEADER = 11
LOCALE = "Plum Boro"
TWENTY_FOUR_START = 12
SLEEP = 's'
WAKE  = 'w'
CLEAR = ("clear", "cls")[platform.system() == "Windows"]
TRUE  = ["true", "t", "1", "on", "yes", "y"]
FALSE = ["false", "f", "0", "off", "no", "n"]

# Option settings
INPUT_TYPE = ".awc"
SLEEP_CRITERIA = (9,10)
WAKE_CRITERIA  = (9,10)
THRESHOLD = [1.0]
TRIM_ZEROES = True
CALC_DAYLIGHT = True

# Command line flags
VERIFICATION = False
TAB_DELIMITED = False
AUTORUN = False
FORMAT_AWC = False
DL = ','
PRINT_OUTPUT = False
READABLE = False

# Analysis variables
ENABLED  = []
DISABLED = [ "sunset","darkStart","sleepStart","SOL",\
			"sunrise","darkEnd","sleepEnd","TWAK",\
			"darkPeriod","sleepPeriod","sleepTST","WASO","SE",\
			"24hourTST","NOC" ]



# string batchRun(string, string)
#   in:     string inputDir
#           string outputFile
#   out:    string error
#
# TODO description
#
def batchRun(inputDir, outputFile):

	# Get input file batch
	inputBatch = [file for file in os.listdir(inputDir) if file.lower().endswith(INPUT_TYPE)]
	if len(inputBatch) == 0:
		return "No " + INPUT_TYPE + " files found in " + os.path.abspath(inputDir)

	# Write standard output headers
	if not VERIFICATION and not FORMAT_AWC:
		try: outputStream = open( os.path.join(outputFile), "w" )
		except IOError: return "Invalid output directory."
		output( "id"+DL+"date", outputStream )
		for var in ENABLED: output( DL + str(var), outputStream )

	# Process each input file
	for inputFile in inputBatch:

		print( "\t" + inputFile + "\t", end="" )
		numDays = 0
	
		# Initialize variables for input data
		inputList    = []
		activityList = []
		videoList    = []
		scoreList    = []
		criteriaList = []

		# Read supported files as input stream
		with open(os.path.join(inputDir, inputFile),"r") as inputStream:
		
			# .awc files
			if INPUT_TYPE == ".awc":
				if VERIFICATION: return "Can only verify .vl.csv files"

				inputList = [line.strip() for line in inputStream]
				monkeyNum = inputList[0]
				sd = inputList[1].split("-")
				st = inputList[2].split(":")

				# supports data from 1980 onwards
				year = int(sd[2])
				if year < 80: year += 2000
				elif year < 100: year += 1900
				
				sdt = datetime.datetime( year, monthToNum(sd[1]), int(sd[0]), int(st[0]), int(st[1]))
				st = sdt.time()

				if TRIM_ZEROES:
					activityList, startTrim, endTrim = trimData(inputList[AWC_HEADER:])
				else:
					activityList, startTrim, endTrim = inputList[AWC_HEADER:], 0, 0
				dateList = getDates(sdt.date(), startTrim, activityList)

			# .vl.csv files
			elif INPUT_TYPE == ".vl.csv":
				if FORMAT_AWC: return "Can only format .awc files"

				inputList = list( list(line) for line in csv.reader(inputStream, delimiter=',') )
				monkeyNum = inputList[1][0]
				sd = inputList[1][1].split("-")
				st = inputList[1][2].split(":")
				sdt = datetime.datetime( int(sd[2]), monthToNum(sd[1]), int(sd[0]), int(st[0]), int(st[1]))
				st = sdt.time()
				for i in range(len(inputList)-1):
					activityList.append(inputList[i+1][3])
					videoList.append(inputList[i+1][4])
				startTrim = endTrim = 0
				dateList = [sdt.date()]

		# Write .awc formatting output headers
		if FORMAT_AWC:
			try: outputStream = open(os.path.join(outputFile, inputFile[:-4] + ".awc.csv" ), "w")
			except IOError: return "Invalid output directory"
			output( "date"+DL+"time"+DL+"activity"+DL+"sleep", outputStream )

		# Classify wake and sleep from actigraphy
		scoreList = coleKripke(THRESHOLD[0], activityList)
		criteriaList = hybridCriteria(scoreList, SLEEP_CRITERIA, WAKE_CRITERIA)
		
		# Compute variables for each night of data
		printID = monkeyNum
		for i in range(len(dateList)):

			numDays += 1
			printDate = str(dateList[i])
			offset = i*1440 - ( minutes(st) + startTrim%1440 )

			# Calculate dark period
			sunset, sunrise = calcSunsetSunrise(dateList[i])
			lightsOff = (19*60)     # 19:00 == 7:00pm
			lightsOn = (7*60)+1440  # 7:00am the following morning
			if CALC_DAYLIGHT:
				if lightsOff > sunset:
					darkStart = lightsOff
				else: darkStart = sunset
				if lightsOn < sunrise:
					darkEnd = lightsOn
				else: darkEnd = sunrise
			else:
				darkStart = lightsOff
				darkEnd = lightsOn
			darkPeriod = darkEnd - darkStart

			darkStart += offset
			darkEnd += offset
			if darkEnd >= len(criteriaList): continue

			# Calculate sleep period
			sleepStart = findSleepStart(criteriaList, darkStart) 
			sleepEnd = findWakeStart(criteriaList, darkEnd)
			sleepPeriod = sleepEnd - sleepStart

			# Calculate latencies and score counts
			SOL = sleepStart - darkStart
			TWAK =  darkEnd - sleepEnd
			sleepTST, WASO = countScores(scoreList, sleepStart, sleepEnd)

			# TODO sleep period wake bouts

			# Calculate sleep efficiency
			darkTST, darkTWT = countScores(scoreList, darkStart, darkEnd)
			try: SE = (darkTST/float(darkPeriod)) * 100
			except: SE = ""

			# Calculate 24 hour variables
			try:
				tfHourTST, tfHourTWT = countScores(scoreList, \
					offset+(TWENTY_FOUR_START*60), offset+(TWENTY_FOUR_START*60)+1440)
				NOC = (darkTST/float(tfHourTST)) * 100
			except: tfHourTST = tfHourTWT = ""

			# Verification output mode
			if VERIFICATION:
				try: outputStream = open(os.path.join(outputFile, inputFile[:-20] + \
					".ver.csv" ),"w")
				except IOError: return "Invalid output directory"

				output( "id"+DL+"date"+DL+"threshold"+DL+"true positives"+DL+"true negatives"+DL+\
					"false positives"+DL+"false negatives"+DL+"total", outputStream )
				for t in range(len(THRESHOLD)):
					scoreList = coleKripke(THRESHOLD[t], activityList)
					compareList = compareToVideo(videoList, scoreList, False, sleepStart, sleepEnd)
					tp, tn, fp, fn, total = verify(compareList)
					output("\n"+str(monkeyNum)+DL+dateList[i]+DL+str(THRESHOLD[t])+DL+str(tp)+\
						DL+str(tn)+DL+str(fp)+DL+str(fn)+DL+str(total), outputStream )

			# .awc formatting output mode
			elif FORMAT_AWC:
				if i==0: printDate = str(dateList[i])
				for t in range(i*1440, (i+1)*1440):
					if (t+minutes(st)+startTrim%1440)%1440==0 and (i+1)<len(dateList):
						printDate = dateList[i+1]
					if t<len(activityList):
						output( "\n"+printDate+DL+clock(t+minutes(startTime)+startTrim%1440)+DL+\
							activityList[t]+DL+scoreList[t], outputStream )
					if t==lightsOff+offset: output( DL+"lightsOff", outputStream )
					if t==lightsOn+offset:  output( DL+"lightsOn", outputStream )
					if t==sunset+offset:    output( DL+"sunset", outputStream )
					if t==sunrise+offset:   output( DL+"sunrise", outputStream )
					if t==sleepStart:       output( DL+"sleepStart", outputStream )
					if t==sleepEnd:         output( DL+"sleepEnd", outputStream )
					if READABLE: printDate = ""

			# Standard output mode
			else:
				pc = ("","%")[READABLE]
				output("\n"+printID+DL+str(dateList[i]), outputStream)
				for var in ENABLED:
					if   var == "sunset": output(DL + clock(sunset), outputStream)
					elif var == "darkStart": output(DL + clock(darkStart-offset), outputStream)
					elif var == "sleepStart": output(DL + clock(sleepStart-offset), outputStream)
					elif var == "SOL": output(DL + str(SOL), outputStream)
					elif var == "sunrise": output(DL + clock(sunrise), outputStream)
					elif var == "darkEnd": output(DL + clock(darkEnd-offset), outputStream)
					elif var == "sleepEnd": output(DL + clock(sleepEnd-offset), outputStream)
					elif var == "TWAK": output(DL + str(TWAK), outputStream)
					elif var == "darkPeriod": output(DL + str(darkPeriod), outputStream)
					elif var == "sleepPeriod": output(DL + str(sleepPeriod), outputStream)
					elif var == "sleepTST": output(DL + str(sleepTST), outputStream)
					elif var == "WASO": output(DL + str(WASO), outputStream)
					elif var == "SE": output(DL + "{:.2f}".format(SE) + pc, outputStream)
					elif var == "24hourTST": output(DL + str(tfHourTST), outputStream)
					elif var == "NOC": output(DL + "{:.2f}".format(NOC) + pc, outputStream)

			#dumb if READABLE: printID = ""
		print(" " + str(numDays) + " days")

	print("\nDone.")
	outputStream.close()
	return



# void output(string, string)
#   in:     string string
#           string stream
#   out:    none
#
# Writes to string to some file output stream, and potentially
# outputs string to console.
#
def output(string, stream):
	if PRINT_OUTPUT: print(string, end="")
	stream.write(string)



# list coleKripke(list, list)
#   in:     list threshold
#           list activityList
#   out:    list scoreList
#
# Classifies minute activity data as wake or sleep by cole-kripke 
# scoring and then comparison against an activity count threshold.
#
def coleKripke(threshold, activityList):

	sumActivity = 0
	scoreList = []

	for i in range(len(activityList)):

		try:

			sumActivity = ( 0.04*int(activityList[i-2]) + 0.2*int(activityList[i-1]) \
			+ 1.0*int(activityList[i]) + 0.2*int(activityList[i+1]) + 0.04*int(activityList[i+2]))

		except: pass

		if (sumActivity<=threshold):
			score = SLEEP
		else:
			score = WAKE

		scoreList.append(score)

	return scoreList



# list hybridCriteria(list, list, list)
#   in:     list scoreList
#           list sleepCriteria
#           list wakeCriteria
#   out:    list criteriaList
#
# Builds criteriaList from scoreList by classifying transitions between
# sleep and wake periods by sleepCriteria and wakeCritera. These criteria
# arguments should take the form of 2-element lists, where criteria[0] is the
# numerator and criteria[1] is the denominator- a given minute in scoreList is
# classified as a transition betweens states if criteria[0] out of the 
# following criteria[1] minutes are scored as the opposite state.
#
def hybridCriteria(scoreList, sleepCriteria, wakeCriteria):

	criteriaList = []
	criteriaScore = '-'
	awake = True
	asleep = True
	
	wn = int(wakeCriteria[0])
	wd = int(wakeCriteria[1]) 
	sn = int(sleepCriteria[0])
	sd = int(sleepCriteria[1])

	lookahead = (wd, sd)[wd<sd]

	for m in range(len(scoreList)):
	
		numSleep = 0
		numWake = 0
		ahead = 0

		for look in range(m, m+lookahead):
			try:
				if (scoreList[look] == SLEEP and ahead < sd):
					numSleep += 1
				elif (scoreList[look] == WAKE and ahead < wd):
					numWake += 1    
			except: pass
			ahead += 1

		if awake and numSleep >= sn:
			criteriaScore = SLEEP
			awake = False
			asleep = True

		elif asleep and numWake >= wn:
			criteriaScore = WAKE
			awake = True
			asleep = False

		else: criteriaScore = '-'

		criteriaList.append(criteriaScore)
	
	return criteriaList



# int findSleepStart(list, int)
#   in:     list criteriaList
#           int offset
#   out:    int startPeriod
#
# Returns index of closest instance of sleep criteria in criteriaList
# to offset minute, first searching backwards then forwards.
#
def findSleepStart(criteriaList, offset):

	found = False
	startPeriod = -1

	# start looking backwards from startPoint argument
	i = offset
	while not found:
		test = criteriaList[i]
		if test == WAKE:    # found start of wake instead
			break
		elif test == SLEEP: # found start of sleep period
			startPeriod = i
			found = True
		if i > 0:
			i -= 1
		else:   # reached beginning of list
			break

	# continue looking forwards
	i = offset
	while not found:
		test = criteriaList[i]
		if test == SLEEP:   # found start of sleep period
			startPeriod = i
			found = True
		if i < len(criteriaList) - 1:
			i += 1
		else:   # reached end of list
			startPeriod = -1
			break

	return startPeriod



# int findWakeStart(list, int)
#   in:     list criteriaList
#           int offset
#   out:    int startPeriod
#
# Returns index of closest instance of wake criteria in criteriaList
# to offset minute, first searching backwards then forwards.
#
def findWakeStart(criteriaList, offset):

	found = False
	startPeriod = 1320

	# start looking backwards from startPoint argument
	i = offset
	while not found:
		test = criteriaList[i]
		if test == SLEEP:   # found start of sleep instead
			break
		elif test == WAKE: # found start of wake period
			startPeriod = i
			found = True
		if i > 0:
			i -= 1
		else:   # reached beginning of list
			break

	# continue looking forwards
	i = offset
	while not found:
		test = criteriaList[i]
		if test == WAKE:    # found start of wake period
			startPeriod = i
			found = True
		if i < len(criteriaList) - 1:
			i += 1
		else:   # reached end of list
			break

	return startPeriod



# int, int countScores(list, int, int)
#   in:     list scoreList
#           int start
#           int end
#   out:    int numSleep
#           int numWake
#
# Counts the number of minutes of sleep and wake in scoreList
# between start and end indices
#
def countScores(scoreList, start, end):

	numSleep = 0
	numWake  = 0

	for i in range(start, end):
		try:
			if scoreList[i] == SLEEP: numSleep += 1
			elif scoreList[i] == WAKE: numWake += 1
		except: pass

	return numSleep, numWake



# list compareList(list, list, boolean, int, int)
#   in:     list videoList
#           list scoreList
#           boolean zeroPoint
#           int compareStart
#           int compareEnd
#   out:    list compareList
#
# Compares each minute of data in scoreList against videoList
# between indices compareStart and compareEnd, taking into account
# whether zeroPoint threshold mode is active. Returns a list of
# true/false positive/negatives comparisons
#
def compareToVideo(videoList, scoreList, zeroPoint, compareStart, compareEnd):

	compareList = []
	sleep = SLEEP
	if zeroPoint:
		sleep = '0'

	for i in range(compareStart, compareEnd):
		
		score = scoreList[i] 
		video = videoList[i]
		compare = ''
		if video:

			# Valid
			if video == '3' and score == sleep:
				compare = 'tp'
			elif video == '1' and score != sleep:
				compare = 'tn'

			# Invalid
			elif video == '1' and score == sleep:
				compare = 'fp'

			elif video == '3' and score != sleep:

				compare = 'fn'

		compareList.append(compare)

	return compareList



# int, int, int, int, int verify(list)
#   in:     list compareList
#   out:    int truePos
#           int trueNeg
#           int falsePos
#           int falseNeg
#           int totalCompares
#
# Counts verification statistics in comparison list.
#
def verify(compareList):

	truePos   = trueNeg  = 0
	falsePos  = falseNeg = 0
	accuracy  = sensitivity = specificity = 0
	totalCompares = 0

	for i in range(len(compareList)):

		compare = compareList[i]
		if compare:
			totalCompares += 1
		if(compare == 'tp'):
			truePos += 1
		elif(compare == 'tn'):
			trueNeg += 1
		elif(compare == 'fp'):
			falsePos += 1
		elif(compare == 'fn'):
			falseNeg += 1

	accuracy    = (truePos+trueNeg)/float(totalCompares)*100
	sensitivity =  truePos/float(truePos + falseNeg)*100
	specificity =  trueNeg/float(trueNeg + falsePos)*100

	#return accuracy, sensitivity, specificity, totalCompares
	return truePos, trueNeg, falsePos, falseNeg, totalCompares



# int, int calcSunsetSunrise(string)
#   in:     string dateStr
#   out:    int sunset
#           int sunrise
#
# Uses astral module to calculate number of minutes from midnight
# on given date to sunset and following sunrise.
#
def calcSunsetSunrise(date):

	a = Astral()
	a.solar_depression = "civil"
	city = a[LOCALE]
	timezone = city.timezone

	# get sunset time on given date
	sun  = city.sun(date, local = True)
	sunset  = sun["sunset"]


	# get sunrise time on following morning
	date += datetime.timedelta(days=1)
	sun  = city.sun(date, local = True)
	sunrise = sun["sunrise"]

	# format as number of minute from midnight on dateStr
	sunset  = (sunset.hour*60  + sunset.minute)
	sunrise = (sunrise.hour*60 + sunrise.minute + 1440)
	return sunset, sunrise



# list, int, int trimData(list)
#   in:     list inputList
#   out:    list inputList
#           int startTrim
#           int endTrim
#
# Counts runs of zeroes at start and end of inputList, ignoring first/last 30 
# minutes and ignoring 2 minute activity bouts. If there are more than some
# threshold of zeroes, trims the list.
#
def trimData(inputList):

	# will trim the list if there are more than threshold 0's at start
	threshold = 300
	ignore    = 30
	startTrim = 0
	endTrim   = 0
	# Currently ignoring 30 minutes at start and end, and 2 minute activity bouts

	# count zeros forward from 30 min after list starts
	i = 0
	count = 0
	while inputList[i+ignore]=="0" or inputList[i+ignore+1]=="0" or inputList[i+ignore+2]=="0":
		i += 1

	if i > threshold:
		startTrim = i + ignore
		inputList = inputList[startTrim:]   # trim

	length = len(inputList)

	# count zeroes backwards from 30 min before list ends
	i = 0
	count = 0
	while inputList[length-1-i-ignore]=="0" or inputList[length-2-i-ignore]=="0" \
	or inputList[length-3-i-ignore]=="0":
		count += 1
		i += 1

	if i > threshold:
		endTrim = i + ignore
		inputList = inputList[:length-endTrim]

	return inputList, startTrim, endTrim



# int monthToNum(string)
#   in:     string month
#   out:    int num
#
# Converts a string calender month to numerical value.
#
def monthToNum(month):

	mon = month.lower()
	if mon in ["jan", "january"]:
		return 1
	elif mon in ["feb", "febr" "february"]:
		return 2
	elif mon in ["mar", "march"]:
		return 3
	elif mon in ["apr", "april"]:
		return 4
	elif mon in ["may"]:
		return 5
	elif mon in ["jun", "june"]:
		return 6
	elif mon in ["jul", "july"]:
		return 7
	elif mon in ["aug", "august"]:
		return 8
	elif mon in ["sep", "sept", "september"]:
		return 9
	elif mon in ["oct", "october"]:
		return 10
	elif mon in ["nov", "november"]:
		return 11
	elif mon in ["dec", "december"]:
		return 12
	else:
		return -1



# string numToMonth(int)
#   in:     int num
#   out:    string month
#
# Converts numerical month to string month abbreviation.
#
def numToMonth(num):

	month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
	if num in range(1, 13):
		return month[num-1]
	else:
		return "error"



# list getDates(list, int, list)
#   in:     list startDate
#           int startTrim
#           list inputList
#   out:    list dateList
#
# Returns a list of string dates covered by inputList, using startDate as the 
# date of the first minute, and excluding days trimmed by startTrim
#
def getDates(currDate, startTrim, inputList):

	dateList = []
	currDate += datetime.timedelta(days = startTrim//1440)

	numMins = len(inputList)
	numDays = (numMins//1440) + 1

	for d in range(numDays):

		dateList.append(currDate)
		currDate += datetime.timedelta(days = 1)

	return dateList



# string clock(int)
#   in:     int minutes
#   out:    string clock
#
# Converts a number of minutes to a string containing 24 hour clock time in
# format HH:MM:SS
#
def clock(minutes):
	hour = str((minutes//60)%24)
	minute = minutes%60
	if minute < 10:
		minute = "0" + str(minute)
	else:
		minute = str(minute)

	if READABLE: return hour + ":" + minute + ":00"
	else: return str(int(hour)*60 + int(minute))



# int minutes(string)
#   in:     string clock
#   out:    int minutes
#
# Converts a string containing a 24 hour clock time of format HH:MM:SS or HH:MM
# to a number of minutes after midnight.
#
def minutes(t):
	clock = [t.hour, t.minute]
	if len(clock) == 2:
		return sum( [a*b for a,b in zip( [60, 1], map(int, clock) )] )
	elif len(clock) == 3:
		return sum( [a*b for a,b in zip( [60, 1, 0], map(int, clock) )] )
	else:
		return -1



# boolean isValidDir(string)
#   in:     string dirName
#   out:    boolean valid
#
# Returns whether or not a string contains characters that render it an
# invalid directory name.
#
def isValidDir(dirName):
	badChars = [ "<",">",":","|","?","*","\"" ]
	invalid = [char for char in badChars if char in dirName]
	return invalid



# void showSplash()
#   in:     none
#   out:    none
#
# Prints out the program name, current version, copyright information,
# and other relevant information.
#
def showSplash():
	print("Actigraphy Sleep Variable Analysis | Version " + VERSION)
	print("Developed by Matt Ragoza and Mario Pongibove")
	print("Copyright 2015 Cameron Lab, University of Pittsburgh\n")


# string, list getCommand()
#   in:     none
#   out:    string command
#           list arguments
#
# Gets a list of strings separated by white space from command line input,
# groups together strings that were surrounded by quotation marks "", and
# adds these strings to argument list. The first argument is returned as
# the command, the following are the arguments.
#
def getCommand():

	# Get user input and split strings by whitespace
	print(PROMPT, end="")
	line = input().replace('\n', '')
	pre = list(filter(None, line.split(" ")))
	if len(pre) == 0: return []

	inString = False
	builder = []
	string = ""
	arguments = []
	
	# Add single strings and "grouped strings" to arguments list
	for arg in pre:

		if arg[0] == '\"':
			inString = True

		if inString:
			builder.append(arg)
		else:
			arguments.append(arg)

		if arg[len(arg)-1] == '\"':
			inString = False

			for s in builder:
				string += (s+" ")

			arguments.append(string[1:-2])
			builder = []
			string = ""

	return arguments



# void commandHelp(list)
#   in:     list arguments
#   out:    none
#
# Prints all recognized commands, their argument format, and their functionality.
#
def commandHelp(arguments):
	print("Commands:\n")
	print("\toptions\t\tDisplay current option settings")
	print("\tset <opt> <val>\tSet analysis options")
	print("\tvariables\t\tDisplay variable definitions")
	print("\tenable <var>\tView or add to enabled variables")
	print("\tdisable <var>\tView or add to disabled variables")
	print("\trun <in> <out>\tWrite analysis of input directory to output file")
	print("\t\t<flags>")
	print("\t\t-v\toutput verification statistics instead of standard vars")
	print("\t\t-t\tuse tab delimiters instead of commas")
	print("\t\t-a\tautorun the output file when analysis is finished")
	print("\t\t-f\toutput formatted activity files with additonal info")
	print("\t\t-p\tprints output to console as well as to output file")
	print("\t\t-r\toutput more readable times and subject IDs")
	print("\tquit\t\tTerminate the program (can also use ctrl+C)\n")



# void commandOptions(list)
#   in:     list arguments
#   out:    none
#
# Prints global variables and their current settings.
#
def commandOptions(arguments):
	print("Options:\n")
	print("\tLOCALE\t\t" + str(LOCALE))
	print("\tINPUT_TYPE\t" + str(INPUT_TYPE))
	print("\tTHRESHOLD\t" + str(THRESHOLD)[1:-1])
	print("\tSLEEP_CRITERIA\t" + str(SLEEP_CRITERIA[0])+"/"+str(SLEEP_CRITERIA[1]))
	print("\tWAKE_CRITERIA\t" + str(WAKE_CRITERIA[0])+"/"+str(WAKE_CRITERIA[1]))
	print("\tTRIM_ZEROES\t" + str(TRIM_ZEROES))
	print("\tCALC_DAYLIGHT\t" + str(CALC_DAYLIGHT) + "\n")



# void commandSet(list)
#   in:     list arguments
#   out:    none
#
# Sets the value of a global variable.
#
def commandSet(arguments):

	global LOCALE
	global INPUT_TYPE
	global THRESHOLD
	global SLEEP_CRITERIA
	global WAKE_CRITERIA
	global TRIM_ZEROES
	global VERIFICATION
	global EXAMINE
	global DL
	global CALC_DAYLIGHT

	if len(arguments) < 2:
		print("Requires option and value to set.\n")

	elif arguments[0] == "LOCALE":
		temp = LOCALE
		LOCALE = arguments[1]
		try:
			Astral()[LOCALE]
			print("LOCALE set to " + LOCALE + "\n")
		except KeyError:
			print("Locale was not recognized by astralmod.py\n")
			LOCALE = temp

	elif arguments[0] == "INPUT_TYPE":
		if arguments[1] in SUPPORTED_TYPES:
			INPUT_TYPE = str(arguments[1])
			print("INPUT_TYPE set to " + INPUT_TYPE + "\n")
		else:
			print("Supported input types:", end="")
			for t in SUPPORTED_TYPES: print(" " + t, end="")
			print("\n")

	elif arguments[0] == "THRESHOLD":
		try:
			THRESHOLD = [float(t) for t in arguments[1:]]
			print("THRESHOLD set to " + str(THRESHOLD)[1:-1] + "\n")
		except ValueError: print("Invalid threshold value.\n")

	elif arguments[0] == "SLEEP_CRITERIA":
		tempCriteria = arguments[1].split('/')
		try:
			tempCriteria = [int(i) for i in tempCriteria]
			if len(tempCriteria) != 2 or tempCriteria[0]>tempCriteria[1]:
				print("Invalid criteria setting.\n")
			else:
				SLEEP_CRITERIA = tempCriteria
				print("SLEEP_CRITERIA set to " + str(SLEEP_CRITERIA[0])+"/"+str(SLEEP_CRITERIA[1]) + "\n")
		except ValueError: print("Invalid criteria setting.\n")

	elif arguments[0] == "WAKE_CRITERIA":
		tempCriteria = arguments[1].split('/')
		try:
			tempCriteria = [int(i) for i in tempCriteria]
			if len(tempCriteria) != 2 or tempCriteria[0]>tempCriteria[1]:
				print("Invalid criteria setting.\n")
			else:
				WAKE_CRITERIA = tempCriteria
				print("WAKE_CRITERIA set to " + str(WAKE_CRITERIA[0])+"/"+str(WAKE_CRITERIA[1]) + "\n")
		except ValueError: print("Invalid criteria setting.\n")

	elif arguments[0] == "TRIM_ZEROES":
		if arguments[1].lower() in TRUE:
			TRIM_ZEROES = True
			print("TRIM_ZEROES set to " + str(TRIM_ZEROES) + "\n")
		elif arguments[1].lower() in FALSE:
			TRIM_ZEROES = False
			print("TRIM_ZEROES set to " + str(TRIM_ZEROES) + "\n")
		else: print("Invalid boolean value.\n")

	elif arguments[0] == "CALC_DAYLIGHT":
		if arguments[1].lower() in TRUE:
			CALC_DAYLIGHT = True
			print("CALC_DAYLIGHT set to " + str(TRIM_ZEROES) + "\n")
		elif arguments[1].lower() in FALSE:
			CALC_DAYLIGHT = False
			print("CALC_DAYLIGHT set to " + str(TRIM_ZEROES) + "\n")
		else: print("Invalid boolean value.\n")

	else: print("Option " + arguments[0] + " does not exist.\n")



# void commandVars(list)
#   in:     list arguments
#   out:    none
#
# Prints all analysis variables and their definitions.
#
def commandVars(arguments):
	print("Variables:\n")
	print("\tsunset\t\tTime of sunset on a given date in LOCALE.")
	print("\tsunrise\t\tTime of sunrise on a given date in LOCALE.")
	print("\tdarkStart\tThe last minute of light, given as 19:00, or compared\n\t\t\tagainst " + \
		"sunset if CALC_DAYLIGHT is applied.")
	print("\tdarkEnd\t\tThe first minute of light, given as 7:00, or compared\n\t\t\tagainst " + \
		"sunrise if CALC_DAYLIGHT is applied.")
	print("\tdarkPeriod\tThe number of minutes from darkStart to darkEnd.")
	print("\tsleepStart\tClosest instance of "+str(SLEEP_CRITERIA[0])+"/"+str(SLEEP_CRITERIA[1])+\
		" minutes asleep to darkStart,\n\t\t\tdefined by SLEEP_CRITERIA.")
	print("\tsleepEnd\tClosest instance of "+str(WAKE_CRITERIA[0])+"/"+str(WAKE_CRITERIA[1])+\
		" minutes awake to darkEnd,\n\t\t\tdefined by WAKE_CRITERIA.")
	print("\tsleepPeriod\tThe number of minutes from sleepStart to sleepEnd.")
	print("\tsleepTST\tThe number of minutes scored as sleep during the\n\t\t\tsleepPeriod.")
	print("\tWASO\t\tWake after sleep onset, number of wake minutes in\n\t\t\tsleepPeriod.")
	print("\tSOL\t\tSleep onset latency, number of minutes from darkStart\n\t\t\tto sleepStart.")
	print("\tTWAK\t\tTime awake before light, number of minutes from\n\t\t\tsleepEnd to darkEnd.")
	print("\tSE\t\tSleep efficiency, the percent of darkPeriod scored\n\t\t\tas sleep.")
	print("\t24hourTST\tTotal number of minutes of sleep in a 24 hour period.")
	print("\tNOC\t\tNocturnal sleep consolidation, percent of 24 hour\n\t\t\tsleep in darkPeriod.\n")



# void commandEnable(list)
#   in:     list arguments
#   out:    none
#
# Includes a variable in the next analysis and prints all enabled variables.
#
def commandEnable(arguments):
	for var in arguments:
		if var == "all":
			while(DISABLED):
				ENABLED.append(DISABLED[0])
				DISABLED.remove(DISABLED[0])
		elif var in DISABLED:
			ENABLED.append(var)
			DISABLED.remove(var)
	print("Enabled variables:\n")
	if len(ENABLED) == 0:
		print("\tNone")
	else:
		for var in ENABLED: print("\t"+var)
	print("")



# void commandDisable(list)
#   in:     list arguments
#   out:    none
#
# Excludes a variable from the next analysis and prints all disabled variables.
#
def commandDisable(arguments):
	for var in arguments:
		if var == "all":
			while(ENABLED):
				DISABLED.append(ENABLED[0])
				ENABLED.remove(ENABLED[0])
		elif var in ENABLED:
			DISABLED.append(var)
			ENABLED.remove(var)
	print("Disabled variables:\n")
	if len(DISABLED) == 0:
		print("\tNone")
	else:
		for var in DISABLED: print("\t"+var)
	print("")



# void commandRun(list)
#   in:     list arguments
#   out:    none
#
# Runs a batch analysis on an input directory and writes to output file(s).
# Arguments are <flags*> <input path> <output path>
#
# Optional flags:
#   -v :    Substitute variables analysis for verification, which compares
#               minute actigraphy to videography. Outputs one .ver.csv file
#               per night of input data in .vl.csv format.
#   -t :    Use tab as delimiter in output files instead of comma
#   -a :    Opens the output file/folder automatically on completion
#   -f :    Substitute variabe analysis for .awc formatting, which outputs
#               raw lists of minute times, activity, scores, and events.
#               Outputs one .awc.csv file per input .awc file.
#   -p :    Prints output to console as it writes it to file
#   -r :    Outputs more human-readable data    
#
def commandRun(arguments):

	global VERIFICATION
	global DL
	global AUTORUN
	global FORMAT_AWC
	global PRINT_OUTPUT
	global READABLE

	if "-v" in arguments:
		VERIFICATION = True
		arguments.remove("-v")
	else: VERIFICATION = False

	if "-t" in arguments:
		DL = '\t'
		arguments.remove("-t")
	else: DL = ','

	if "-a" in arguments:
		AUTORUN = True
		arguments.remove("-a")
	else: AUTORUN = False

	if "-f" in arguments:
		FORMAT_AWC = True
		arguments.remove("-f")
	else: FORMAT_AWC = False

	if "-p" in arguments:
		PRINT_OUTPUT = True
		arguments.remove("-p")
	else: PRINT_OUTPUT = False

	if "-r" in arguments:
		READABLE = True
		arguments.remove("-r")
	else: READABLE = False

	if len(arguments) < 2:
		print("Requires input directory and output file.\n")
		return
	else:

		inputDir = arguments[0]
		if not os.path.isdir(inputDir):
			print("Input directory not found.\n")
			return
		if len(arguments) > 1: outputFile = arguments[1]

		if not ENABLED and not VERIFICATION and not FORMAT_AWC:
			print("No output variables enabled.\n")
			return

		print("Running analysis of " + INPUT_TYPE + " files in " + os.path.abspath(inputDir))
		print("Writing output to " + os.path.abspath(outputFile) + "\n")
		error = batchRun(inputDir, outputFile)
		if error: print("\nError: " + error)
		elif AUTORUN:
			print("Starting " + os.path.abspath(outputFile))
			os.system( "start \"\" \"" + outputFile.replace('/','\\') + "\"" )
		print("")



# void cli()
#   in:     none
#   out:    none
#
# Implements a command line interface, allowing user to enter commands
# and arguments that modify the program's settings, input, and output
# and then run custom analyses. Called at program launch.
#
def cli():
	
	arguments = [""]
	print (os.getcwd())
	showSplash()

	#if len(sys.argv)>1:
	#	stream = open(str(sys.argv[1]), "r")
	#else:
	#	stream = sys.stdin

	while True:

		try:
			arguments = getCommand()
 
			if   len(arguments) == 0: 		pass
			elif arguments[0] == "help":    commandHelp(arguments[1:])
			elif arguments[0] == "options": commandOptions(arguments[1:])
			elif arguments[0] == "set":     commandSet(arguments[1:])
			elif arguments[0] == "variables":commandVars(arguments[1:])
			elif arguments[0] == "enable":  commandEnable(arguments[1:])
			elif arguments[0] == "disable": commandDisable(arguments[1:])
			elif arguments[0] == "run":     commandRun(arguments[1:])
			elif arguments[0] == "quit":    break
			else: print ("Command not recognized, try \"help\".\n")

		except KeyboardInterrupt: break

	return

if __name__ == "__main__" : cli()
