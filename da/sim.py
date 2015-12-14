# Copyright (c) 2010-2015 Bo Lin
# Copyright (c) 2010-2015 Yanhong Annie Liu
# Copyright (c) 2010-2015 Stony Brook University
# Copyright (c) 2010-2015 The Research Foundation of SUNY
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os
import abc
import sys
import copy
import time
import queue
import signal
import random
import logging
import threading
import traceback
import multiprocessing

from argparse import Namespace
from . import pattern, common, endpoint, config

builtin = common.builtin

InstanceLogFormatter = logging.Formatter(
    '[%(asctime)s]%(name)s[%(instance)s]:%(levelname)s: %(message)s')

class DistProcess(multiprocessing.Process):
    """Abstract base class for DistAlgo processes.

    Each instance of this class enbodies the runtime activities of a DistAlgo
    process in a distributed system. Each process is uniquely identified by a
    two-ary tuple (address, port), where 'address' is the name or IP of the
    host machine and 'port' is an integer corresponding to the port number on
    which this process listens for incoming messages from other DistAlgo
    processes. Messages exchanged between DistAlgo processes are instances of
    `DistMessage`.

    DistAlgo processes can spawn more processes by calling `createprocs()`.
    The domain of `DistProcess` instances are flat, in the sense that all
    processes are created "equal" -- no parent-child relationship is
    maintained. Any DistProcess can send messages to any other DistProcess,
    given that it knows the unique id of the target process. However, the
    terminal is shared between all processes spawned from that terminal. This
    includes the stdout, stdin, and stderr streams. In addition, each
    DistProcess also maintains a TCP connection to the master control node
    (the first node started in a distributed system) where DistAlgo commands
    are passed (see `distalgo.runtime.proto`).

    Concrete subclasses of `DistProcess` must define the functions:

    - `setup`: A function that initializes the process-local variables.

    - `main`: The entry point of the process. This function defines the
      activities of the process.

    Users should not instantiate this class directly, process instances should
    be created by calling `createprocs()`.

    """

    class Comm(threading.Thread):
        """The background communications thread.

        Creates an event object for each incoming message, and appends the
        event object to the main process' event queue.
        """

        def __init__(self, parent):
            threading.Thread.__init__(self)
            self._parent = parent

        def run(self):
            try:
                for msg in self._parent._recvmesgs():
                    try:
                        (src, clock, data) = msg
                    except ValueError as e:
                        self._parent._log.warn(
                            "Invalid message dropped: {0}".format(str(msg)))
                        continue

                    e = pattern.ReceivedEvent(
                        envelope=(clock, None, src),
                        message=data)
                    self._parent._eventq.put(e)

            except KeyboardInterrupt:
                pass

    def __init__(self, node, initpipe, props=None):
        multiprocessing.Process.__init__(self)

        self.id = None
        self._running = False
        self._node = node
        self._initpipe = initpipe

        self._configurations = Namespace()
        self._cmdline = common.global_options()
        if props is not None:
            self._properties = props
        else:
            self._properties = dict()

        self._events = []
        self._timer = None
        self._timer_expired = False
        self._lock = None
        self._setup_called = False

        # Configurations:
        self._logical_clock = None
        self._handling = None
        self._channel = endpoint.UdpEndPoint

        # Performance counters:
        self._usrtime_st = 0
        self._systime_st = 0
        self._waltime_st = 0
        self._usrtime = 0
        self._systime = 0
        self._waltime = 0
        self._is_timer_running = False
        self._sent_msgs = 0

        self._dp_name = self._properties.get('name', None)
        self._log = logging.getLogger(self.__class__.__name__)

        self._child_procs = []

    def _wait_for_go(self):
        self._log.debug("Sending id to parent...")
        self._initpipe.send(self.id)
        while True:
            act = self._initpipe.recv()

            if act == "start":
                self._running = True
                del self._initpipe
                self._log.debug("'start' command received, commencing...")
                return
            else:
                inst, args = act
                if inst == "setup":
                    if self._setup_called:
                        self._log.warn(
                            "setup() already called for this process!")
                    else:
                        self._log.debug("Running setup..")
                        self.setup(*args)
                        self._setup_called = True
                else:
                    m = getattr(self, "set_" + inst)
                    m(*args)

    def _start_comm_thread(self):
        self._eventq = queue.Queue()
        self._comm = DistProcess.Comm(self)
        self._comm.daemon =True
        self._comm.start()

    def _sighandler(self, signum, frame):
        for cpid, _ in self._child_procs:
            os.kill(cpid, signal.SIGTERM)
        sys.exit(0)

    def _get_config(self, key, default=None):
        """Returns the configuration value corresponding to `key'.

        Command line parameters takes highest precedence, followed by process
        configurations, and finally module level configurations.

        """
        cmdparam = getattr(self._cmdline, key)
        if cmdparam is not None:
            return cmdparam
        if hasattr(self._configurations, key):
            return getattr(self._configurations, key)
        try:
            this_mod = sys.modules[self._cmdline.this_module_name]
            if hasattr(this_mod._Configurations, key):
                return getattr(this_mod._Configurations, key)
        except KeyError as e:
            self._log.error("Can not locate current module object.")
        return default

    def _init_config(self):
        """Set configuration variables.

        """
        # Clock:
        clock = self._get_config("clock", 'lamport').lower()
        if clock == 'lamport':
            self._logical_clock = 0
        else:
            self._log.warn("Unsupported logical clock type %s.", str(clock))

        # Handling:
        handling = self._get_config("handling", "one").lower()
        if handling == "one":
            self._handling = config.HandlingOne
        elif handling == "all":
            self._handling = config.HandlingAll
        elif handling == "snapshot":
            self._handling = config.HandlingSnapshot
        else:
            self._log.warn("Unknown handling type %s.", str(handling))
            self._handling = config.HandlingOne

        # Channel:
        channel = self._get_config("channel", [])
        if not isinstance(channel, list):
            channel = [channel]
        for prop in channel:
            prop = prop.lower()
            if prop == 'fifo' or prop == 'reliable':
                self._channel = endpoint.TcpEndPoint
            elif prop not in {'nonfifo', 'unreliable'}:
                self._log.error("Unknown channel property %s", str(prop))
        return

    def run(self):
        try:
            self._cmdline.this_module_name = self.__class__.__module__
            if multiprocessing.get_start_method() == 'spawn':
                common.set_global_options(self._cmdline)
                common.sysinit()

            self._init_config()
            self.id = self._channel(self._dp_name, self.__class__)
            common.set_current_process(self.id)
            pattern.initialize(self.id)
            signal.signal(signal.SIGTERM, self._sighandler)

            self._start_comm_thread()
            self._lock = threading.Lock()
            self._lock.acquire()
            self._wait_for_go()

            if not hasattr(self, '_da_run_internal'):
                self._log.error("Process class %s missing entry point!" %
                                self.__class__.__name__)
                sys.exit(1)

            result = self._da_run_internal()
            self.report_times()

        except Exception as e:
            sys.stderr.write("Unexpected error at process %s:%r"% (str(self), e))
            traceback.print_tb(e.__traceback__)

        except KeyboardInterrupt as e:
            self._log.debug("Received KeyboardInterrupt, exiting")
            pass

    def start_timers(self):
        if not self._is_timer_running:
            self._usrtime_st, self._systime_st, _, _, _ = os.times()
            self._waltime_st = time.clock()
            self._is_timer_running = True

    def stop_timers(self):
        if self._is_timer_running:
            usrtime, systime, _, _, _ = os.times()
            self._usrtime += usrtime - self._usrtime_st
            self._systime += systime - self._systime_st
            self._waltime += time.clock() - self._waltime_st
            self._is_timer_running = False

    def report_times(self):
        if self._node is not None:
            self._node.put((self.id, ('totalusrtime', self._usrtime)))
            self._node.put((self.id, ('totalsystime', self._systime)))
            self._node.put((self.id, ('totaltime', self._waltime)))
            self._node.put((self.id, ('sent', self._sent_msgs)))

    @builtin
    def exit(self, code=0):
        raise SystemExit(code)

    @builtin
    def output(self, *value, sep=' ', level=logging.INFO):
        """Prints arguments to the process log.

        Optional argument 'level' is a positive integer that specifies the
        logging level of the message, defaults to 'logging.INFO'(20). Refer to
        [https://docs.python.org/3/library/logging.html#levels] for a list of
        predefined logging levels.

        When the level of the message is equal to or higher than the
        configured level of a log handler, the message is logged to that
        handler; otherwise, it is ignored. DistAlgo processes are
        automatically configured with two log handlers:, one logs to the
        console, the other to a log file; the handlers' logging levels are
        controlled by command line parameters.

        """
        msg = sep.join([str(v) for v in value])
        self._log.log(level, msg)

    @builtin
    def work(self):
        """Waste some random amount of time."""
        time.sleep(random.randint(0, 200) / 100)
        pass

    @builtin
    def logical_clock(self):
        """Returns the current value of Lamport clock."""
        return self._logical_clock

    @builtin
    def incr_logical_clock(self):
        """Increment Lamport clock by 1."""
        if isinstance(self._logical_clock, int):
            self._logical_clock += 1

    @builtin
    def spawn(self, pcls, args, **props):
        """Spawns a child process"""
        childp, ownp = multiprocessing.Pipe()
        p = pcls(self._node, childp, props)
        p.daemon = True
        p.start()

        childp.close()
        cid = ownp.recv()
        ownp.send(("setup", args))
        ownp.send("start")

        return cid

    # Wrapper functions for message passing:
    def _send(self, data, to):
        self.incr_logical_clock()
        if (self._fails('send')):
            self.output("Simulated send fail: %s" % str(data), logging.WARNING)
            return

        if (hasattr(to, '__iter__')):
            targets = to
        else:
            targets = [to]
        for t in targets:
            t.send(data, self.id, self._logical_clock)

        self._trigger_event(pattern.SentEvent((self._logical_clock,
                                               to, self.id),
                                              copy.deepcopy(data)))
        self._sent_msgs += 1

    def _recvmesgs(self):
        for mesg in self.id.recvmesgs():
            if self._fails('receive'):
                self.output("Simulated receive fail: %s" % str(mesg),
                            logging.WARNING)
            else:
                yield mesg

    def _timer_start(self):
        self._timer = time.time()
        self._timer_expired = False

    def _timer_end(self):
        self._timer = None

    def _fails(self, failtype):
        if failtype not in self._properties:
            return False
        if (random.random() < self._properties[failtype]):
            return True
        return False

    def _label(self, name, block=False, timeout=None):
        """This simulates the controlled "label" mechanism.

        Each label marks a `yield point'.

        """
        # Handle performance timers first:
        if name == "start":
            self.start_timers()
        elif name == "end":
            self.stop_timers()
        if self._fails('hang'):
            self.output("Hanged(@label %s)" % name, logging.WARNING)
            self._lock.acquire()
        if self._fails('crash'):
            self.output("Crashed(@label %s)" % name, logging.WARNING)
            self.exit(10)

        # Handle "all" and `block' at the same time makes no sense, because it
        # will loop forever. Only handle "all" if non-blocking:
        if self._handling is config.HandlingAll and not block:
            while self._process_event(False, name, timeout):
                pass
        elif self._handling is config.HandlingSnapshot:
            snapshot = self._eventq.qsize()
            while snapshot > 0 and self._process_event(block, name, timeout):
                snapshot -= 1
        else:
            # Default is handling one:
            self._process_event(block, name, timeout)

    def _process_event(self, block, label=None, timeout=None):
        """Retrieves and processes pending messages.

        Parameter 'block' indicates whether to block waiting for next message
        to come in if the queue is currently empty. 'timeout' is the maximum
        time to wait for an event.

        """
        if timeout is not None:
            if self._timer is None:
                self._timer_start()
            timeleft = timeout - (time.time() - self._timer)
            if timeleft <= 0:
                self._timer_end()
                self._timer_expired = True
                return False
        else:
            timeleft = 0

        try:
            event = self._eventq.get(block, timeleft)
        except queue.Empty:
            return False
        except Exception as e:
            self._log.error("Caught exception while waiting for events: %r", e)
            return False

        self._update_logical_clock(event)
        self._trigger_event(event, label)
        return True

    def _update_logical_clock(self, event):
        """Update our logical clock value based on `event'.

        `event' should be a received message from a remote peer.

        """
        # FIXME: currently only Lamport's clock is implemented.

        if isinstance(self._logical_clock, int):
            if not isinstance(event.timestamp, int):
                # Most likely some peer did not turn on lamport clock, issue
                # a warning and skip this message:
                self._log.warn(
                    "Invalid logical clock value: {0}; message dropped. "
                    "".format(event.timestamp))
                return
            self._logical_clock = max(self._logical_clock, event.timestamp) + 1

    def _trigger_event(self, event, label=None):
        """Immediately triggers `event'.

        """
        self._log.debug("triggering event %s" % event)
        for p in self._events:
            bindings = dict()
            if (p.match(event, bindings=bindings,
                        ignore_bound_vars=True, **self.__dict__)):
                if p.record_history is True:
                    getattr(self, p.name).append(event.to_tuple())
                elif p.record_history is not None:
                    # Call the update stub:
                    p.record_history(getattr(self, p.name), event.to_tuple())
                for h in p.handlers:
                    if ((h._labels is None or label in h._labels) and
                        (h._notlabels is None or label not in h._notlabels)):
                        try:
                            h(**copy.deepcopy(bindings))
                        except TypeError as e:
                            self._log.error(
                                "%s when calling handler '%s' with '%s': %s",
                                type(e).__name__, handler.__name__,
                                str(args), str(e))
                    else:
                        self._log.debug(
                            "Event %s for handler %s skipped due to label "
                            "restriction.", str(event), str(h)
                        )

    def _forever_message_loop(self):
        while (True):
            self._process_event(block=True, label=None, timeout=None)

    def __str__(self):
        s = self.__class__.__name__
        if self._dp_name is not None:
            s += "[" + self._dp_name + "]"
        else:
            s += "[" + str(self.id) + "]"
        return s

    ### Various attribute setters:
    def set_name(self, name):
        self._dp_name = name
