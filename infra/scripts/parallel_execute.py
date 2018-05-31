#!/usr/bin/env python

import datetime
import threading
import time
from optparse import OptionParser
import subprocess
import sys

PARSER = OptionParser()
PARSER.add_option('--interleave-output', '-i', dest='interleave_output',
                  default=False,
                  action='store_true',
                  help='Set on to interleave output')
PARSER.add_option('--retries', dest='retries',
                  default=0,
                  type='int',
                  help='Number of retries if failure')
PARSER.add_option('--seconds-between-retries', dest='seconds_between_retries',
                  default=0,
                  type='int',
                  help='Number of seconds to wait between retries')
PARSER.add_option('--no-prefix', dest='no_prefix',
                  default=False,
                  action='store_true',
                  help='Output the prefix (default with interleaved)')
PARSER.add_option('--no-timestamp', dest='no_timestamp',
                  default=False,
                  action='store_true',
                  help='Do not print timestamp')
PARSER.add_option('--max-secs-run', '-s', dest='max_secs_run',
                  default=None,
                  type='float',
                  help='Number of seconds allowed before running processes are killed')
PARSER.add_option('--secs-idle-to-kill', '-k', dest='secs_idle_to_kill',
                  default=None,
                  help='Number of seconds allowed before killing the thread')


WAIT_QUANTA = 0.17  # polling


def get_time_str():
    if not OPTIONS.no_timestamp:
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return ''


class KilledProcessesException(Exception):
    pass


class RunnerThread(threading.Thread):
    def __init__(self, id, cmd):
        threading.Thread.__init__(self)
        self.id = id
        self.cmd = cmd
        self.tries = OPTIONS.retries + 1
        self.start_timestamp = 0
        self.last_output_timestamp = 0
        self.subprocess = None
        self.output_buffer = list()
        #self.output_lock = threading.Lock()
        self.lines = 0
        self._return_code = None

    def run(self):
        self.start_timestamp = time.time()
        self.process_data()

    def process_data(self):
        while self.tries > 0:
            self.output_buffer.append(
                (get_time_str(), "shell$ %s\n" % self.cmd))
            self.subprocess = subprocess.Popen(self.cmd,
                                               shell=True,
                                               stdout=subprocess.PIPE,
                                               stderr=subprocess.STDOUT)
            while True:
                try:
                    line = self.subprocess.stdout.readline()  # blocking call
                    if line != '':  # every line should have '\n' at minimum
                        #self.output_lock.acquire()
                        self.output_buffer.append((get_time_str(), line,))
                        self.last_output_timestamp = time.time()
                        self.lines += 1
                        #self.output_lock.release()
                    else:
                        break
                except:
                    print "Unexpected error:", sys.exc_info()[0]
                    break

            self._return_code = self.subprocess.poll()
            if self._return_code == 0:
                break  # successful process returns 0
            self.tries -= 1
            if self.tries > 0:
                self.output_buffer.append(
                    (get_time_str(),
                     '[FAILURE] Return code of %s, retrying...\n' % self._return_code))
                time.sleep(OPTIONS.seconds_between_retries)

    def print_output_queue(self):
        #self.output_lock.acquire()
        if len(self.output_buffer) > 0:
            for tstamp, line in self.output_buffer:
                print tstamp,
                if not OPTIONS.no_prefix:
                    print "[%s]" % self.id,
                print line,
            del self.output_buffer[:]
        #self.output_lock.release()

    def print_finish(self):
        print (get_time_str() + " [%s]" % self.id),
        print ('[SUCCESS]' if self._return_code == 0 else '[FAILURE]'),
        print "return_code:%s%s, seconds:%d, lines:%d" % (
            self._return_code,
            '(normal)' if self._return_code == 0 else '(error)',
            self.last_output_timestamp - self.start_timestamp,
            self.lines)


def terminatel_processes_if_necessary(runners, latest_output_time, start_time):
    if (OPTIONS.max_secs_run is not None and
            OPTIONS.max_secs_run < (latest_output_time - start_time)):
        print("ERROR: exceeding %s seconds, terminating processes..." %
              OPTIONS.max_secs_run)
        for runner in runners:
            print("%s [%s] [TERMINATING] %s" %
                  (get_time_str(), runner.id, runner.cmd))
            try:
                runner.subprocess.terminate()
            except:
                print "Unexpected error:", sys.exc_info()[0]
        time.sleep(WAIT_QUANTA * 10)
        for runner in runners:
            try:
                runner.subprocess.kill()
            except:
                print "Unexpected error:", sys.exc_info()[0]
            runner.print_output_queue()
        raise KilledProcessesException()


def main():
    global OPTIONS
    (OPTIONS, args) = PARSER.parse_args()

    if len(args) == 0:
        PARSER.print_help()
        sys.exit(0)

    # sequential output
    print get_time_str(),
    if OPTIONS.interleave_output:
        print "Interleaved output."
    else:
        print "Sequential output mode. All threads are in parallel."

    start_time = latest_output_time = time.time()
    runners = []
    for i, cmd in enumerate(args):
        runner = RunnerThread(i + 1, cmd)
        print get_time_str(),
        print '[%s] [STARTING] %s' % (runner.id, runner.cmd)
        runner.start()
        runners.append(runner)

    try:
        if OPTIONS.interleave_output:
            _runners = list(runners)
            while len(_runners) > 0:
                for runner in _runners:
                    runner.print_output_queue()
                    latest_output_time = max(latest_output_time, runner.last_output_timestamp)
                for runner in _runners:
                    if len(runner.output_buffer) == 0 and not runner.is_alive():
                        _runners.remove(runner)
                        runner.print_finish()
                time.sleep(WAIT_QUANTA)
                terminatel_processes_if_necessary(_runners, latest_output_time, start_time)
        else:
            # sequential output (from parallel run)
            print ""
            for runner in runners:
                while True:
                    runner.print_output_queue()
                    latest_output_time = max(latest_output_time,
                                             runner.last_output_timestamp)
                    if (len(runner.output_buffer) == 0 and
                            runner.subprocess is not None):
                        if not runner.is_alive():
                            break
                    terminatel_processes_if_necessary(runners,
                                                      latest_output_time,
                                                      start_time)
                    time.sleep(WAIT_QUANTA)
                runner.print_finish()
                if runner != runners[-1]:
                    print ""
                    print "===================================================="
                    print ""
    except KilledProcessesException:
        pass

    exit_statuses = [r.subprocess.poll() for r in runners]
    final_return_code = reduce(lambda x, y: x | y, exit_statuses)
    print '%s return code is a composite of all the processes. Bitwise %s = %s' % (
        get_time_str(),
        '|'.join(map(lambda i: str(i), exit_statuses)),
        final_return_code
    )
    if final_return_code > 0:
        failed_job_numbers = []
        for i, status_code in enumerate(exit_statuses):
            if status_code > 0:
                failed_job_numbers.append('[%d]' % (i + 1))
        print
        print('Error: Job %s (out of %d jobs) failed.'
              ' Please review the failures above.' %
              (', '.join(failed_job_numbers),
               len(exit_statuses)))
    sys.exit(final_return_code)


if __name__ == '__main__':
    sys.stdout.flush()
    main()
