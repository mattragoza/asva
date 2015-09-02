import datetime as dt
import sys
import os
import argparse
import glob
import pytz
import ephem

DELIMITER = ','
AWC_COL_ORDER = ['id_', 'datetime', 'date', 'time', 'activity',
                 'state', 'transition']
VAR_COL_ORDER = ['id_', 'date',
                 'light_start', 'sleep_end', 'TWAK',
                 'light_end', 'sleep_start', 'SOL']

SLEEP_M = 's'
WAKE_M  = 'w'
NONE_M = None

SLEEP_T = 'asleep'
WAKE_T = 'wake up'
NONE_T = ''

ACTIGRAM = False
ACT_SYMBOL = '='
ACT_UNIT = 10

CALC_DAYLIGHT = True
# 709 New Texas Rd, Pittsburgh, PA 15213
LOCATION = {'latitude':'40.45', 'longitude':'-79.17', 'timezone':'US/Eastern', 'elevation':361.74}

class Count:

    def __init__(self, val):
        self.val = int(val)

    def __repr__(self):
        if ACTIGRAM:
            return ACT_SYMBOL * (self.val//ACT_UNIT)
        else:
            return str(self.val)


class AWC:

    """
    A representation of a columnar actigraphy data file, which contains
    an 11-row header followed by minute-by-minute actigraphy.
    """

    def __init__(self, filepath, read=True, given=None):

        self.source = filepath
        self.index = 0

        if read:
            self.original = True
            stream = open(filepath, "r")
            header = [next(stream).strip('\n') for i in range(11)]
            counts = [count.strip('M\n') for count in stream]
            stream.close()
            
            self.id_ = header[0]
            self.start_dt = dt.datetime.strptime(header[1] + ' ' + header[2], '%d-%b-%Y %H:%M')
            self.activity = [Count(val) for val in counts]
            self.state = None
            self.transition = None

        else:
            self.original = False
            self.id_        = given['id_']
            self.start_dt   = given['start_dt']
            self.activity   = given['activity']
            self.state      = given['state']
            self.transition = given['transition']

    def score(self, threshold): # Cole Kripke algorithm

        state = [NONE_M] * len(self)
        mult  = [0.04, 0.2, 1.0, 0.2, 0.04]

        for i in range(2, len(self)-2):

            sum_activity = sum([m * a.val for m, a in zip(mult, self.activity[i-2:i+3])])

            if sum_activity <= threshold:
                state[i] = SLEEP_M
            else:
                state[i] = WAKE_M

        self.state = state

    def find_periods(self, criteria):

        criteria = [int(c) for c in criteria.split('/')]
        transition = [NONE_T] * len(self)
        asleep = True
        awake  = True
        num_sleep = 0
        num_wake  = 0
        for i in range(len(self) - criteria[1]):

            # front of sliding window adds to tally
            if self.state[i] is SLEEP_M:
                num_sleep += 1
            elif self.state[i] is WAKE_M:
                num_wake += 1

            # rear of sliding window subtracts from tally
            if i >= criteria[1]:
                if self.state[i - criteria[1]] is SLEEP_M:
                    num_sleep -= 1
                elif self.state[i - criteria[1]] is WAKE_M:
                    num_wake -= 1

            # don't find transitions on minutes with no sleep/wake state
            if not self.state[i - criteria[1] + 1]:
                continue

            if asleep and num_wake >= criteria[0]:
                asleep = False
                awake  = True
                transition[i - criteria[1] + 1] = WAKE_T
            elif awake and num_sleep >= criteria[0]:
                asleep = True
                awake  = False
                transition[i - criteria[1] + 1] = SLEEP_T

        self.transition = transition

    def datetime(self, i):
        return self.start_dt + dt.timedelta(minutes=i)

    def date_range(self):

        end_date = self.datetime(len(self))
        num_dates = round((end_date - self.start_dt).total_seconds()/(24*3600))
        return ((self.start_dt + dt.timedelta(days=x)).date()
                for x in range(num_dates+1))

    def __iter__(self):
        self.index = 0
        return self

    def __next__(self):
        try:
            row = self[self.index]
            self.index += 1
        except IndexError:
            raise StopIteration
        return row

    def __str__(self):
        s = self.source + '\n'
        for l in AWC_COL_ORDER:
            s += l + DELIMITER
        s += '\n'
        for row in self:
            row.label = False
            s += repr(row)
            row.label = True
        return s

    def __repr__(self):
        if self.original:
            return self.source
        else:
            return str(self)

    def __len__(self):
        return len(self.activity)

    def __getitem__(self, i):

        """
        The AWC object is abstractly represented as a table of minute
        data. Indexing the object returns a row of single minute values,
        and either integer indices or datetimes (and ranges) can be used.
        """

        end_dt = self.datetime(len(self))

        if isinstance(i, int):
            if not i in range(len(self)):
                raise IndexError('list index out of range')
            cols = {}
            cols['id_'] = self.id_
            curr_dt = self.datetime(i)
            cols['datetime'] = curr_dt
            cols['date'] = curr_dt.date()
            cols['time'] = curr_dt.time()
            cols['activity'] = self.activity[i]
            if self.state: cols['state'] = self.state[i]
            if self.transition: cols['transition'] = self.transition[i]
            row = self.AWCRow(cols)

        elif isinstance(i, str):
            find_dt = dt.datetime.strptime(i, '%Y-%m-%d %H:%M')
            if find_dt >= self.start_dt and find_dt < end_dt:
                i = int((find_dt - self.start_dt).total_seconds()//60)
            else: raise IndexError('datetime index out of bounds')
            row = self[i]

        elif isinstance(i, slice):
            start = i.start
            stop  = i.stop
            step  = i.step

            if isinstance(start, str):
                find_dt = dt.datetime.strptime(start, '%Y-%m-%d %H:%M')
                if find_dt >= self.start_dt and find_dt < end_dt:
                    start = int((find_dt - self.start_dt).total_seconds()//60)
                else: raise IndexError('start datetime out of bounds')

            if isinstance(stop, str):
                find_dt = dt.datetime.strptime(stop, '%Y-%m-%d %H:%M')
                if find_dt >= self.start_dt and find_dt < end_dt:
                    stop = int((find_dt - self.start_dt).total_seconds()//60)
                else: raise IndexError('stop datetime out of bounds')
            
            data = {}
            data['id_'] = self.id_
            data['start_dt'] = self.datetime(start)
            data['activity'] = self.activity[start:stop]
            if self.state: data['state'] = self.state[start:stop]
            else: data['state'] = None
            if self.transition: data['transition'] = self.transition[start:stop]
            else: data['transition'] = None
            row = AWC(filepath=self.source, read=False, given=data)

        return row

    class AWCRow:

        """
        Represents a single minute observation from the parent actigraphy
        data. The column values are stored in a dictionary and printed
        out by the order found in the COL_ORDER list.
        """

        def __init__(self, cols):
            self.cols = cols
            self.label = True

        def __len__(self):
            return len(self.cols)

        def __getitem__(self, i):
            return self.cols[i]
            
        def __repr__(self):
            s = ""
            if self.label:
                for name in AWC_COL_ORDER:
                    s += name + DELIMITER
                s += '\n'
            for v in AWC_COL_ORDER:
                s += str(self[v]) + DELIMITER
            return s + '\n'

    # below are some basic conditions for filtering

    def has_datetime(self, dt):

        try: return self[dt]
        except IndexError:
            return False

    def is_id(self, id_):
        return self.id_ == id_



class Frame:

    """
    A simple data structure for applying filters and functions
    to multiple AWC file objects.
    """

    def __init__(self, awcs):

        self.awcs = awcs
        self.vars_ = []

    def filter(self, by, args=None):

        res = Frame([awc for awc in self.awcs if by(awc, args)])
        return res

    def score(self, threshold):

        for awc in self.awcs:
            awc.score(threshold)

    def find_periods(self, criteria):

        for awc in self.awcs:
            awc.find_periods(criteria)



    def compute_variables(self): # let's try to do this in ONE pass

        vars_ = []
        for awc in self.awcs:

            # minute-offset of AWC start time from 0:00:00 on start date
            start_offset = 60*awc.start_dt.hour + 1*awc.start_dt.minute
            day_i = 0
            end_dt = awc.datetime(len(awc)) 

            for date in awc.date_range():

                light_start, light_end = light_period(date)
                last_asleep, last_awake = None, None
                sleep_start, sleep_end = None, None
                SOL, TWAK = None, None

                for i in range(1440):

                    try: # to look at minute i of current date
                        curr = awc[day_i + (i-start_offset)]

                        if awc.start_dt <= light_start and curr['transition'] is WAKE_T:
                            test_TWAK = min_diff(curr['datetime'], light_start)
                            if not sleep_end or abs(test_TWAK) < abs(TWAK):
                                sleep_end = curr['datetime']
                                TWAK = test_TWAK

                        elif light_end < end_dt and curr['transition'] is SLEEP_T:
                            test_SOL = min_diff(light_end, curr['datetime'])
                            if not sleep_start or abs(test_SOL) < abs(SOL): # something wrong with this?
                                sleep_start = curr['datetime']
                                SOL = test_SOL

                    except IndexError: continue

                
                if light_start: light_start = light_start.time()
                if light_end: light_end = light_end.time()
                if sleep_start: sleep_start = sleep_start.time()
                if sleep_end: sleep_end = sleep_end.time()

                vars_.append(self.VarRow({
                    'id_':awc.id_,
                    'date':date,
                    'light_start':light_start,
                    'light_end':light_end,
                    'sleep_start':sleep_start,
                    'sleep_end':sleep_end,
                    'SOL':SOL,
                    'TWAK':TWAK
                    }))

                day_i += 1440
      
        self.vars_ = vars_

    class VarRow:

        def __init__(self, cols):
            self.cols = cols

        def __len__(self):
            return len(self.cols)

        def __getitem__(self, i):
            return self.cols[i]
            
        def __repr__(self):
            s = ""
            for v in VAR_COL_ORDER:
                s += str(self[v]) + DELIMITER
            return s + '\n'

    def trim_zeroes(self, edge, sequence, allow):

        # TODO
        pass

    def __getitem__(self, i):

        if isinstance(i, int):
            return self.awcs[i]

        elif isinstance(i, str):
            for awc in self.awcs:
                if i == awc.source:
                    return awc
            raise KeyError('does not contain an AWC from that source')

    def __repr__(self):
        s = str(len(self)) + ' .awc files\n'
        for awc in self.awcs:
            s += repr(awc) + '\n'
        return s

    def __str__(self):
        s= ''
        for i in VAR_COL_ORDER:
            s += i + DELIMITER
        s += '\n'
        for row in self.vars_:
            s += repr(row)
        return s

    def __len__(self):
        return len(self.awcs)



def light_period(date):

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


def min_diff(dt_i, dt_f): # between 2 datetimes

    return (dt_f - dt_i).total_seconds()//60


if __name__ == '__main__':

    argv = sys.argv
    parser = argparse.ArgumentParser(
        prog=__file__,
        description='Actigraphy sleep variable analysis tool.',
        epilog=None)
    parser.add_argument('FILE_PATTERN')
    parser.add_argument('--threshold', '-t', type=float)
    parser.add_argument('--criteria', '-c', type=str)
    parser.add_argument('--output', '-o')

    # positional arg FILE_PATTERN is required, regardless of pipe
    if not sys.stdin.isatty(): argv.insert(1, None)
    args = parser.parse_args(argv[1:])

    if args.FILE_PATTERN: # get files matching a pattern
        files = glob.glob(args.FILE_PATTERN)
    else: # or get files from pipe
        files = [f.strip() for f in sys.stdin.readlines()]

    try:
        if args.output:
            stream = open(args.output, 'w')
        else:
            stream = sys.stdout

        # Read input files into AWC objects and Frame them
        print("Formatting data", file=sys.stderr)
        data = Frame([AWC(f, read=True) for f in files])

        # Score all actigraphy data
        print("Scoring actigraphy", file=sys.stderr)
        data.score(threshold=(1.0, args.threshold)[bool(args.threshold)])

        # Use criteria to find sleep/wake transitions
        print("Finding sleep/wake periods", file=sys.stderr)
        data.find_periods(criteria=('9/10',args.criteria)[bool(args.criteria)])

        # TODO: calculate analysis variables
        print("Computing sleep variables", file=sys.stderr)
        data.compute_variables()

        print(str(data), file=stream)
        stream.close()

    except BrokenPipeError:
        pass # Ignore premature end-of-pipe

    except IOError as e:
        print(e)

    # Exit success
    sys.exit(0)