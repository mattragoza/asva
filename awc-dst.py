# DAY LIGHT SAVINGS PREPROCESSOR FOR AWC FILES
# version 1 as of 9/12/14
# written by Matt Ragoza

import sys
import platform
import csv
import os
import glob
import time
import math
import datetime
import pytz
import astral
from astral import Astral
reload(astral)

CLEAR = ('clear', 'cls')[bool(platform.system() == 'Windows')]
SPRING_LIST = [ "2-Apr-2000", "1-Apr-2001", "7-Apr-2002", "6-Apr-2003", "4-Apr-2004", "3-Apr-2005", "2-Apr-2006", "11-Mar-2007", "9-Mar-2008", "8-Mar-2009", "14-Mar-2010", "13-Mar-2011", "11-Mar-2012", "10-Mar-2013", "9-Mar-2014", "8-Mar-2015", "13-Mar-2016", "12-Mar-2017", "11-Mar-2018", "10-Mar-2019" ]
FALL_LIST   = [ "29-Oct-2000", "28-Oct-2001", "27-Oct-2002", "26-Oct-2003", "31-Oct-2004", "30-Oct-2005", "29-Oct-2006", "4-Nov-2007", "2-Nov-2008", "1-Nov-2009", "7-Nov-2010", "6-Nov-2011", "4-Nov-2012", "3-Nov-2013", "2-Nov-2014", "1-Nov-2015", "6-Nov-2016", "5-Nov-2017", "4-Nov-2018", "3-Nov-2019" ]

def main():
	
	os.system(CLEAR)

	# Print current path
	print("Currently in " + os.getcwd())
	
	# Prompt user for input directory
	print("\n--- DST PREPROCESSOR FOR AWC FILES ---\n")
	inDir = raw_input("Enter the directory with activity files: ")
	if not os.path.isdir(inDir):
		print("Couldn't find that directory.")
		return

	# Prompt user for output directory
	outDir = raw_input("Name the output directory: ")
	if outDir is "":
		outDir = "."
	if not is_valid_dir(outDir):
		print("Invalid directory.")
		return

	# Find or create the output directory
	if not os.path.isdir(outDir):
		os.makedirs(outDir)
	
	# Call the main sleep scoring function
	find_dst_transitions(inDir, outDir)



def find_dst_transitions(inDir, outDir):

	# Get list of files to process and keep track of errors and success rate
	files = [file for file in os.listdir(inDir) if file.lower().endswith(".awc")]
	totalFiles  = len(files)
	doneFiles   = 0
	errorList   = []

	# For each .awc file in the input directory,
	for inFile in files:

		doneFiles += 1

		# Set up processing display
		os.system(CLEAR)
		print str(doneFiles) + "/" + str(totalFiles) + " .awc files processed"
		print str(len(errorList)) + " errors"
		barLength = 72
   		progress  = barLength * doneFiles / totalFiles
   		print "o" * progress + "-" * (barLength - progress)

		# Initialize lists for input data
		dateList     = []
		inputList    = []
		activityList = []

		# Read the contents of file to inputList
		inputStream = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), inDir, inFile), "r")
		inputList   = [line.strip() for line in inputStream]
		inputStream.close()

		# Parse file information
		header = 11
		monkeyNum  = inputList[0]
		dateString = inputList[1]
		timeString = inputList[2]
		startTime  = sum([a*b for a,b in zip([60, 1], map(int, timeString.split(':')))])
		activityList = inputList[header:]

		# Calculate dates for days of activity data
		duration = len(activityList)
		days = (duration/1440) + 1
		date = dateString.split('-')
		day   = int(date[0])
		month = month_to_num(date[1])
		year  = int(date[2])
		for d in range(0, days):
			dateString = str(day) + "-" + num_to_month(month) + "-" + str(year)
			dateList.append(dateString)
			# Handle end of the month and year while incrementing date
			if (month in [4, 6, 9, 11] and day == 30) or (month == 2 and day == 28) or day == 31:
				day = 0
				if month == 12:
					month = 0
					if year == 99:
						year = -1
					year += 1
				month += 1
			day += 1

		# For each day of data,
		for d in range(len(dateList)):

			day = dateList[d]
			noon = (720-startTime) + d*1440

			if day in SPRING_LIST:

				# Spring forward
				try:
					
					# Write .awc file for prior to noon on day of switch
					outFile = inFile[:-4] + "[standard].awc"
					outputStream = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), outDir, outFile), "w")
					standardList = activityList[:noon]
					for i in range(len(standardList) + header):
						if i < header:
							outputStream.write(inputList[i] + "\n")
						else:
							outputStream.write(standardList[i-header] + "\n")

					# Write .awc file for after noon on day of switch
					outFile = inFile[:-4] + "[DST].awc"
					outputStream = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), outDir, outFile), "w")
					DSTList = activityList[noon:]
					for i in range(len(DSTList) + header):
						if i < header:
							if i==1:
								outputStream.write(day + "\n")
							elif i==2:
								outputStream.write("13:00\n")		# Set the clock forward
							else:
								outputStream.write(inputList[i] + "\n")
						else:
							outputStream.write(DSTList[i-header] + "\n")

				except:
   					print "\nError: %s<" % sys.exc_info()[0]
				
			elif day in FALL_LIST:

				# Fall back
				try:

					# Write .awc file for prior to noon on day of switch
					outFile = inFile[:-4] + "[DST].awc"
					outputStream = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), outDir, outFile), "w")
					DSTList = activityList[:noon]
					for i in range(len(DSTList) + header):
						if i < header:
							outputStream.write(inputList[i] + "\n")
						else:
							outputStream.write(DSTList[i-header] + "\n")

					# Write .awc file for after noon on day of switch
					outFile = inFile[:-4] + "[standard].awc"
					outputStream = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), outDir, outFile), "w")
					standardList = activityList[noon:]
					for i in range(len(standardList) + header):
						if i < header:
							if i==1:
								outputStream.write(day + "\n")
							elif i==2:
								outputStream.write("11:00\n")		# Set the clock back
							else:
								outputStream.write(inputList[i] + "\n")
						else:
							outputStream.write(standardList[i-header] + "\n")

				except:
   					print "\nError: %s<" % sys.exc_info()[0]

	print "\nErrors:"
	for e in errorList:
		print e
	print "-"


def trim_data(inputList):

	# will trim the list if there are more than threshold 0's at start
	threshold = 300
	ignore    = 30
	startTrim = 0
	endTrim   = 0
	length = len(inputList)

	# count zeros forward from 30 min after list starts
	i = 0
	count = 0
	while inputList[i+ignore] == "0" or inputList[i+ignore+1] == "0":
		i += 1
	print i

	if i > threshold:
		startTrim = i + ignore
		inputList = inputList[startTrim:]	# trim
		print "list start was trimmed by " + str(startTrim)
		time.sleep(0.4)

	# count zeroes backwards from 30 min before list ends
	i = 0
	count = 0
	while inputList[length-1-i-ignore] == "0" or inputList[length-2-i-ignore] == "0":
		count += 1
		i += 1
	print i

	if i > threshold:
		endTrim = i + ignore
		inputList = inputList[:length-endTrim]
		print "list end was trimmed by " + str(endTrim)
		time.sleep(0.4)

	# return the trimmed list and the amount the beginning was trimmed, to offset start time
	return inputList, startTrim, endTrim


def calc_sunset_sunrise(dateStr):

	global LOCALE

	a = Astral()
	a.solar_depression = "civil"
	city = a[LOCALE]
	timezone = city.timezone
	
	date  = dateStr.split('-')
	day   = int(date[0])
	month = month_to_num(date[1])
	year  = int(date[2])

	# get sunset time on given date
	date = datetime.datetime(year, month, day)
	sun  = city.sun(date, local = True)
	sunset  = sun["sunset"]

	# get sunrise time on following morning
	date += datetime.timedelta(days=1)
	sun  = city.sun(date, local = True)
	sunrise = sun["sunrise"]

	# format as minutes after 6:00PM marker
	sunset  = (sunset.hour*60  + sunset.minute - 1080)
	sunrise = (sunrise.hour*60 + sunrise.minute + 360)

	return sunset, sunrise


def is_valid_dir(dir):
	badChars = ["<",">",":","|","?","*","\""]
	invalid = [c for c in badChars if c in dir]
	return not invalid


def month_to_num(month):
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


def num_to_month(num):
	months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
	if num in range(1, 13):
		return months[num-1]
	else:
		return "error"


# Program loop
while True:
	main()
	time.sleep(0.2)
	if not raw_input("\nAgain? ").lower() in ["yes", "y", "ok"]:
		os.system(CLEAR)
		break