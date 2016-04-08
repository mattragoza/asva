from __future__ import print_function
import datetime as dt
import sys
import os
import re
import argparse
import glob
import pytz
import ephem

# rearrange the order of these lists to modify the order of
# columns in the output csv
AWC_COL_ORDER = ['id_', 'datetime', 'activity', 'state', 'transition']
VAR_COL_ORDER = ['id_', 'date', 'dark_start', 'sleep_start', 'SOL',
                 'dark_end', 'sleep_end', 'TWAK', 'dark_period', 'sleep_period',
                 'dark_TST', 'sleep_TST', 'TST', 'WASO', 'SE', 'NOC', 'notes']
DELIMITER = (' ', ',')[__name__ == '__main__']
MISSING_VALUE = 'null'
OMIT_PROBLEMS = True

SLEEP_MIN = 's'
WAKE_MIN  = 'w'
SLEEP_TRANS = 'S'
WAKE_TRANS  = 'W'

CALC_DAYLIGHT = True
LOCATION = {'latitude': '40.45', 'longitude': '-79.17',
            'timezone': 'US/Eastern', 'elevation': 361.74}

def main(argv=sys.argv[1:]):

    args, extra = parse_args(argv)

    if extra:
        print('error: received ' + str(len(extra)) + ' extra arguments', \
            file=sys.stderr)
        print('make sure to quote file patterns with spaces or wildcards', \
            file=sys.stderr)
        return 1
    elif args.file_pattern:
        files = glob.glob(args.file_pattern)
    else:
        files = [line.rstrip() for line in sys.stdin]

    if len(files) == 0:
        print('error: no input files were found', file=sys.stderr)
        print('check that the file pattern is correct', file=sys.stderr)
        return 1

    try:
        out = open(args.output, 'w')
    except IOError:
        print('error: could not access output file ' + args.output, file=sys.stderr)
        print('it might be opened in another process', file=sys.stderr)
        return 1
    except TypeError:
        out = sys.stdout

    awc_data = ActigraphyDatabase(files, args.threshold, args.criteria, args.light_period)
    if awc_data.vars:
        print(awc_data, file=out)
    else:
        print("error: no data to write", file=sys.stderr)
    out.close()

    return 0

def parse_args(argv):

    parser = argparse.ArgumentParser(
        prog=__file__,
        description='Actigraphy sleep variable analysis utility.',
        epilog=None)
    parser.add_argument('file_pattern', type=str, \
        help='glob-style file pattern to get AWC files as input')
    parser.add_argument('--threshold', '-t', type=float, default=1.0, \
        help='activity threshold for classifying sleep and wake states in each minute; default is 1.0')
    parser.add_argument('--criteria', '-c', type=str, default='9/10', \
        help='ratio of states needed for a transition between sleep and wake periods; default is 9/10')
    parser.add_argument('--output', '-o', type=str, \
        help='path to output sleep variables in csv format; default is to print to stdout')
    parser.add_argument('--light_period', '-l', type=str, default='7:00:00,19:00:00', \
        help='lights on and off times in 24-hour HH:MM:SS,HH:MM:SS format')
    if not sys.stdin.isatty():
        argv.insert(0, '')

    return parser.parse_known_args(argv)


class AWC:

    '''Wrapper for a columnar actigraphy data file, which contains
    an 11-row header followed by minute actigraphy data.'''

    def __init__(self, file_):

        self.file = file_
        with open(file_, 'r') as fp:

            # parse the first 11 lines as header info
            header = [next(fp).strip('\n') for _ in range(11)]           
            self.id_ = header[0].rstrip() or None
            self.start_dt = dt.datetime.strptime(\
                header[1].strip() + ' ' + header[2].strip(), '%d-%b-%Y %H:%M')

            # the rest of the file contains activity counts
            self.activity = [int(re.sub(r'[^0-9]', '', c)) for c in fp]
            self.state = None
            self.transition = None

            self.end_dt = self.datetime_at_index(len(self))

    def score(self, threshold):

        '''Uses Cole-Kripke algorithm to classify minutes as sleep or
        wake, by first applying a smoothing function and then comparing 
        to a threshold.'''

        self.state = [None] * len(self)
        wt = [0.04, 0.2, 1.0, 0.2, 0.04]

        for i in range(2, len(self)-2):

            # weighted sum of a 5 minute window around current minute
            act_sum = sum([m*a for m, a in zip(wt, self.activity[i-2:i+3])])

            # threshold check
            if act_sum <= threshold:
                self.state[i] = SLEEP_MIN
            else:
                self.state[i] = WAKE_MIN

        return self.state

    def find_periods(self, criteria):

        '''Finds transitions between sleep and wake states as defined by
        the criteria argument, which says that a transition to sleep while
        awake occurs in a given minute if at least <criteria numerator>
        minutes in the next <criteria denominator> minute window were
        scored as sleep minutes, and vice versa.'''

        criteria = [int(i) for i in criteria.split('/')]
        if len(criteria) != 2:
            raise TypeError('criteria must be in format %d/%d')
        self.transition = [None] * len(self)
        asleep = True
        awake  = True
        num_sleep = 0
        num_wake  = 0
        for i in range(len(self) - criteria[1]):

            # front of sliding window adds to tally
            if self.state[i] == SLEEP_MIN:
                num_sleep += 1
            elif self.state[i] == WAKE_MIN:
                num_wake += 1

            # rear of sliding window subtracts from tally
            if i >= criteria[1]:
                if self.state[i - criteria[1]] == SLEEP_MIN:
                    num_sleep -= 1
                elif self.state[i - criteria[1]] == WAKE_MIN:
                    num_wake -= 1

            if asleep and num_wake >= criteria[0]:
                asleep = False
                awake  = True
                self.transition[i - criteria[1] + 1] = WAKE_TRANS
            elif awake and num_sleep >= criteria[0]:
                asleep = True
                awake  = False
                self.transition[i - criteria[1] + 1] = SLEEP_TRANS

        return self.transition

    def datetime_at_index(self, i):

        '''Returns the datetime at a given number of minutes from
        the start of the AWC file. Does NOT throw IndexError.'''

        return self.start_dt + dt.timedelta(minutes=i)

    def date_range(self):

        '''Returns an inclusive list of dates that are represented
        in this file, ie. not necessarily in their entirety.'''

        num_dates = (self.end_dt-self.start_dt).total_seconds()//(24*3600)
        return [(self.start_dt+dt.timedelta(days=n)).date() \
                for n in range(int(num_dates) + 1)]

    def __len__(self):

        '''The number of minutes of actigraphy covered by this AWC file.'''
        return len(self.activity)


class ActigraphyDatabase:

    '''An interface for applying functions to and computing variables
    across multiple AWC files.'''

    def __init__(self, files, threshold, criteria, light_period):

        self.awcs = []
        self.vars = []

        self.light_start, self.light_end = light_period.split(',')

        if files is not None:
            print("Scoring actigraphy files", file=sys.stderr)
            for file_ in files:
                try:
                    awc = AWC(file_)
                except IOError:
                    print('error: could not access input file ' + file_, file=sys.stderr)
                    continue
                awc.score(threshold)
                awc.find_periods(criteria)
                self.awcs.append(awc)

            print("Computing sleep variables", file=sys.stderr)
            self._compute_variables()

    def _compute_variables(self):

        self.vars = []
        for awc in self.awcs:

            # get minute offset of the AWC start time from midnight on its start date
            start_offset = awc.start_dt.hour*60 + awc.start_dt.minute

            # for each date in the AWC file
            for di, date in enumerate(awc.date_range()):

                # begin creating a row of sleep variables
                row = dict()
                row['id_'] = awc.id_
                row['date'] = date
                row['dark_end'] = None
                row['dark_start'] = None
                row['sleep_end'] = None
                row['sleep_start'] = None
                row['TWAK'] = None
                row['SOL'] = None
                row['dark_period'] = None
                row['dark_TST'] = None
                row['sleep_period'] = None
                row['sleep_TST'] = None
                row['WASO'] = None
                row['TST'] = None
                row['SE'] = None
                row['NOC'] = None
                row['notes'] = ""

                light_start, light_end = light_period(date, self.light_start, self.light_end)
                sleep_start, sleep_end = None, None
                SOL, TWAK = None, None

                # compute when sleep ended and started on the current date
                for mi in range(di*1440, (di + 1)*1440):

                    mi -= start_offset
                    try: awc.activity[mi]
                    except IndexError:
                        continue
                    curr_dt = awc.datetime_at_index(mi)

                    # if light_start is in the AWC, find closest sleep_end to light_start
                    if (awc.start_dt <= light_start and awc.transition[mi] == WAKE_TRANS):

                        test_TWAK = min_diff(curr_dt, light_start)
                        if (sleep_end is None or abs(test_TWAK) < abs(TWAK)):
                            sleep_end = curr_dt
                            TWAK = test_TWAK

                    # if light_end is in the AWC, find closest sleep_start to light_end
                    elif (light_end < awc.end_dt and awc.transition[mi] == SLEEP_TRANS):

                        test_SOL = min_diff(light_end, curr_dt)
                        if (sleep_start is None or abs(test_SOL) < abs(SOL)):
                            sleep_start = curr_dt
                            SOL = test_SOL

                # define start of the dark period and sleep period on this date
                row['dark_start'] = light_end.time()
                if sleep_start is not None:
                    row['sleep_start'] = sleep_start.time()
                    row['SOL'] = SOL

                # try to compute sleep variables for last night
                try:

                    # get the previous row of variables; raises IndexError
                    prev = self.vars[-1]
                    prev_ok = True

                    # check that the previous variable row is from the same AWC file
                    if prev['id_'] != row['id_'] or date != prev['date']+dt.timedelta(days=1):
                        prev_ok = False
                        prev['notes'] = 'END OF AWC FILE'
                        raise ValueError()

                    # determine the length of last night's dark period
                    prev_dark_start = dt.datetime.combine(prev['date'], prev['dark_start'])
                    prev['dark_end'] = light_start.time()
                    prev['dark_period']  = min_diff(prev_dark_start, light_start)

                    # check that last night's sleep period can be established
                    if not (sleep_end and prev['sleep_start']):
                        prev['notes'] = 'UNDEFINED SLEEP PERIOD'
                        raise ValueError()

                    # define the end time and length of last night's sleep period
                    prev_sleep_start = dt.datetime.combine(prev['date'], prev['sleep_start'])
                    prev['TWAK'] = TWAK
                    prev['sleep_end'] = sleep_end.time()
                    prev['sleep_period'] = min_diff(prev_sleep_start, sleep_end)

                    # count sleep minutes from previous noon to current noon
                    TST, dark_TST, sleep_TST = 0, 0, 0
                    for i in range((2*di - 1)*720, (2*di + 1)*720):

                        i -= start_offset
                        try: curr_state = awc.state[i]
                        except IndexError:
                            continue
                        curr_dt = awc.datetime_at_index(i)

                        if curr_state == SLEEP_MIN:
                            TST += 1
                            if prev_dark_start <= curr_dt < light_start:
                                dark_TST += 1
                            if prev_sleep_start <= curr_dt < sleep_end:
                                sleep_TST += 1

                    # define the rest of sleep variables for last night
                    prev['TST'] = TST
                    prev['sleep_TST'] = sleep_TST
                    prev['WASO'] = prev['sleep_period'] - sleep_TST
                    prev['dark_TST'] = dark_TST
                    prev['SE'] = dark_TST/float(prev['dark_period'])

                    if TST == 0:
                        prev['NOC'] = float("inf")
                    else:
                        prev['NOC'] = sleep_TST/float(prev['TST'])

                    # determine faulty actigraphy monitor from sleep_TST
                    if TST < 180 or TST >= 1080:
                        prev['notes'] = 'ABNORMAL ACTIGRAPHY'
                        raise ValueError()

                except IndexError:
                    # just keep going if there's no previous row
                    pass

                except ValueError:
                    if OMIT_PROBLEMS:
                        self.vars.pop()

                # append the row for current date
                self.vars.append(row)

        if self.vars:
            self.vars[-1]['notes'] = 'END OF AWC FILE'
            if OMIT_PROBLEMS:
                self.vars.pop()

        return self.vars

    def filter(self, condition):

        f = ActigraphyDatabase()
        f.vars = [row for row in self.vars if condition(row)]
        return f

    def __repr__(self):

        s = ''
        for col in VAR_COL_ORDER:
            if OMIT_PROBLEMS and col == 'notes':
                continue
            s += col + DELIMITER

        for row in self.vars:
            s += '\n'
            for col in VAR_COL_ORDER:
                if OMIT_PROBLEMS and col == 'notes':
                    continue
                s += str(row[col]).replace('None', MISSING_VALUE) + DELIMITER

        return s


def light_period(date, light_start, light_end):

    '''Get the time of light start or light end on a given date.
    Light start is sunrise or 7:00:00, whichever is earlier.
    Light end is sunset or 19:00:00, whichever is later.'''

    light_start = dt.datetime.combine(date, dt.time(*map(int, light_start.split(':'))))
    light_end = dt.datetime.combine(date, dt.time(*map(int, light_end.split(':'))))

    if CALC_DAYLIGHT: # compare against sunset and sunrise

        local_tz = pytz.timezone(LOCATION['timezone'])
        utc_offset = local_tz.utcoffset(light_start)
        
        observer = ephem.Observer()
        observer.date = date - utc_offset
        observer.lat  = LOCATION['latitude']
        observer.lon  = LOCATION['longitude']
        observer.elev = LOCATION['elevation']
        observer.pressure = 0
        observer.horizon = 0

        sunrise = observer.previous_rising(ephem.Sun())
        sunset  = observer.next_setting(ephem.Sun())

        sunrise = sunrise.datetime() + utc_offset
        sunset = sunset.datetime() + utc_offset

        # TODO this is a hack but these astronomy packages are ridiculous
        sunrise = dt.datetime.combine(date, dt.time(hour=sunrise.hour, minute=sunrise.minute))
        sunset = dt.datetime.combine(date, dt.time(hour=sunset.hour, minute=sunset.minute))

        # check if sunrise is earlier than lights on
        if sunrise < light_start:
            light_start = sunrise

        # check if sunset is later than lights off
        if sunset > light_end:
            light_end = sunset
    
    return light_start, light_end

def min_diff(dt_i, dt_f):

    '''Returns the minute difference between two datetimes.'''

    return int((dt_f - dt_i).total_seconds()//60)

if __name__ == '__main__':
    sys.exit(main())