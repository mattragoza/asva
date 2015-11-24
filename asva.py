import datetime as dt
import sys
import os
import argparse
import glob
import pytz
import ephem

DELIMITER = ','

# rearrange the order of these lists to modify the order of
# columns in the output csv
AWC_COL_ORDER = ['id_', 'datetime', 'activity', 'state', 'transition']
VAR_COL_ORDER = ['id_', 'date', 'light_start', 'light_end',
                 'sleep_end', 'sleep_start', 'TWAK', 'SOL',
                 'dark_period', 'sleep_period',
                 'date_TST', 'dark_TST', 'sleep_TST',
                 'SE', 'NOC']

SLEEP_MIN = 's'
WAKE_MIN  = 'w'
SLEEP_TRANS = 's'
WAKE_TRANS = 'w'
MISSING_DATA = 'null' # what to write

CALC_DAYLIGHT = True
LOCATION = {'latitude': '40.45',
            'longitude': '-79.17',
            'timezone': 'US/Eastern',
            'elevation': 361.74}

def main(argv=sys.argv[1:]):

    settings = parse_args(argv)

    if settings.file_pattern is not None:
        files = glob.glob(settings.file_pattern)
    else:
        files = [line.strip() for line in sys.stdin]

    try:
        out = open(settings.output, 'w')
    except IOError:
        print('error: could not access the output file', file=sys.stderr)
        return 1
    except TypeError:
        out = sys.stdout

    awc_data = ActigraphyDatabase(files, settings.threshold, settings.criteria)

    print(awc_data, file=out)
    out.close()

    return 0

def parse_args(argv):

    parser = argparse.ArgumentParser(
        prog=__file__,
        description='Actigraphy sleep variable analysis tool.',
        epilog=None)
    parser.add_argument('file_pattern')
    parser.add_argument('--threshold', '-t', type=float)
    parser.add_argument('--criteria', '-c', type=str)
    parser.add_argument('--output', '-o', type=str)

    if not sys.stdin.isatty():
        argv.insert(0, None)
    return parser.parse_args(argv)


class AWC:

    '''Wrapper for a columnar actigraphy data file, which contains
    an 11-row header followed by minute actigraphy data.'''

    def __init__(self, file_):

        self.source = file_
        self.index = 0

        with open(file_, "r") as fp:

            # parse the first 11 lines as header info
            header = [next(fp).strip('\n') for _ in range(11)]           
            self.id_ = header[0] or None
            self.start_dt = dt.datetime.strptime(\
                header[1] + ' ' + header[2], '%d-%b-%Y %H:%M')

            # the rest of the file contains activity counts
            self.activity = [int(c.strip('M\n')) for c in fp]
            self.state = None
            self.transition = None

            self.end_dt = self.itodt(len(self))

    def score(self, threshold):

        '''Uses Cole-Kripke algorithm to classify minutes as sleep or
        wake, by first applying a smoothing function and then comparing 
        to a threshold.'''

        if threshold is None:
            threshold = 1.0

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

        if criteria is None:
            criteria = '9/10'

        criteria = [int(i) for i in criteria.split('/')]
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

    def itodt(self, i):

        '''Returns the datetime at a given number of minutes from
        the start of the awc file. Does NOT throw IndexError.'''

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
    for multiple AWC objects.'''

    def __init__(self, files, threshold, criteria):

        self.awcs = []

        for file_ in files:
            awc = AWC(file_)
            awc.score(threshold)
            awc.find_periods(criteria)
            self.awcs.append(awc)

        self._compute_variables()

    def _compute_variables(self):

        self.vars = []
        for awc in self.awcs:

            # minute-offset of AWC start time from 0:00:00 on start date
            start_offset = awc.start_dt.hour * 60 + awc.start_dt.minute
            test_sleep_tst = 0

            # for each date in the awc file
            for date_index, date in enumerate(awc.date_range()):

                # potentially we need to calculate all sleep variables
                light_start, light_end = light_period(date)
                dark_period = None
                sleep_start, sleep_end = None, None
                sleep_period = None
                sol, twak = None, None
                date_tst, dark_tst = 0, 0
                se, noc = None, None

                row = dict()
                row['id_'] = awc.id_
                row['date'] = date
                row['sleep_period'] = None
                row['dark_period'] = None
                row['sleep_TST'] = None
                row['dark_TST'] = None
                row['NOC'] = None
                row['SE'] = None

                # iterate thru the lines in awc that WOULD cover that date
                # there are 1440 lines (minutes) per date
                for i in range(date_index * 1440 - start_offset,
                    (date_index + 1) * 1440 - start_offset):

                    # get the datetime from the line index
                    curr_dt = awc.itodt(i)

                    try:

                        # if this date's light start is in the awc
                        # and we found a wake transition,
                        if (awc.start_dt <= light_start
                            and awc.transition[i] == WAKE_TRANS):

                            test_twak = min_diff(curr_dt, light_start)

                            # if we haven't marked anything as the
                            # end of sleep period yet, or the wake 
                            # is closer to light start than previous wake,
                            if (sleep_end is None
                                or abs(test_twak) < abs(twak)):

                                # mark that minute as end of sleep period
                                # and adjust TWAK to reflect this
                                sleep_end = curr_dt
                                twak = test_twak

                        # else if this date's light end is in the awc
                        # and we found a sleep transition,
                        elif (light_end < awc.end_dt
                            and awc.transition[i] == SLEEP_TRANS):

                            test_sol = min_diff(light_end, curr_dt)

                            # if we haven't marked anything as the
                            # start of sleep period yet, or the sleep
                            # is closer to light end than previous sleep,
                            if (sleep_start is None 
                                or abs(test_sol) < abs(sol)):

                                # mark that minute as start of sleep period
                                # and adjust SOL to reflect this
                                sleep_start = curr_dt
                                sol = test_sol

                        # count total sleep time
                        if awc.state[i] == SLEEP_MIN:
                            date_tst += 1
                            if curr_dt < light_start or curr_dt >= light_end:
                                dark_tst += 1

                    except IndexError:
                        # if the awc has any start offset, IndexErrors will
                        # be raised due to negative indices, so don't break
                        # just keep going until reaching valid indices
                        continue

                try:
                    # if there is a previous date, calculate its dark period
                    # and sleep period variables
                    prev = self.vars[-1]
                    if prev['id_'] != awc.id_ \
                        or date != prev['date'] + dt.timedelta(days=1):
                        raise IndexError()

                    prev_light_end = dt.datetime.combine(
                            prev['date'], prev['light_end'])
                    prev['dark_period'] = min_diff(prev_light_end, light_start)

                    prev_sleep_start = dt.datetime.combine(
                            prev['date'], prev['sleep_start'])
                    prev['sleep_period'] = min_diff(prev_sleep_start,sleep_end)
                    
                    prev_sleep_tst = 0
                    sleep_start_i = min_diff(awc.start_dt, \
                        dt.datetime.combine(prev['date'], prev['sleep_start']))
                    sleep_end_i = min_diff(awc.start_dt, sleep_end)
                    for i in range(sleep_start_i, sleep_end_i):
                        try:
                            if awc.state[i] == SLEEP_MIN:
                                prev_sleep_tst += 1
                        except IndexError:
                            continue

                    prev_dark_tst = 0
                    dark_start_i = min_diff(awc.start_dt, \
                        dt.datetime.combine(prev['date'], prev['light_end']))
                    dark_end_i = min_diff(awc.start_dt, light_start)
                    for i in range(dark_start_i, dark_end_i):
                        try:
                            if awc.state[i] == SLEEP_MIN:
                                prev_dark_tst += 1
                        except IndexError:
                            continue

                    prev['sleep_TST'] = prev_sleep_tst
                    prev['dark_TST'] = prev_dark_tst
                    prev['NOC'] = prev_sleep_tst/float(prev['date_TST'])
                    prev['SE'] = prev_dark_tst/float(prev['dark_period'])

                except (IndexError, TypeError) as e:
                    pass
                
                if light_start:
                    light_start = light_start.time()
                if light_end:
                    light_end = light_end.time()
                if sleep_start:
                    sleep_start = sleep_start.time()
                if sleep_end:
                    sleep_end = sleep_end.time()               

                row['light_start'] = light_start
                row['light_end'] = light_end
                row['sleep_start'] = sleep_start
                row['sleep_end'] = sleep_end
                row['SOL'] = sol
                row['TWAK'] = twak
                row['date_TST'] = date_tst

                self.vars.append(row)
        
        return self.vars

    def trim_zeroes(self, edge, sequence, allow):

        raise NotImplementedError()

    def __str__(self):

        s = ''
        for i in VAR_COL_ORDER:
            s += i + DELIMITER
        for line in self.vars:
            s += '\n'
            for i in VAR_COL_ORDER:
                s += str(line[i]).replace('None', MISSING_DATA) + DELIMITER
        return s


def light_period(date):

    '''Get the time of light start or light end on a given date.
    Light start is sunrise or 7:00:00, whichever is earlier.
    Light end is sunset or 19:00:00, whichever is later.'''

    light_start = dt.datetime.combine(date, dt.time(7, 0, 0))
    light_end = dt.datetime.combine(date, dt.time(19, 0, 0))

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