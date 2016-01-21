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

import io
import sys
import select
import socket
import logging
import ipaddress
import threading

from collections import namedtuple

from .protos import Protocol, TcpProtocol, UdpProtocol

log = logging.getLogger("Endpoint")

class EndPoint:
    """Manages all communication protocols for the current process.

    """

    def __init__(self, name=None, proctype=None):
        if name is None:
            self._name = 'localhost'
        else:
            self._name = name
        self._proc = None
        self._proctype = proctype
        self._log = logging.getLogger("runtime.EndPoint")
        self._address = None
        self._connections = None
        self._lock = None       # LRU is not thread-safe

    def _init_config(self):
        """Initializes global parameters.

        Under 'fork' semantics, this only needs to be done once. However, to
        support 'spawn' semantic we need to do this for every new process.

        """
        from . import common
        opts = common.global_options()
        Protocol.max_retries = opts.max_retries
        Protocol.min_port = opts.min_port
        Protocol.max_port = opts.max_port
        self._connections = common.LRU(opts.max_connections)
        self.host = socket.gethostbyname(self._name)

    def start(self):
        try:
            # 1. initialize configuration variables and lock object. We need
            # to init config here in order to support the `spawn' start
            # method
            self._init_config()
            self._lock = threading.RLock()
            # 2. start the protocols:
            return True
        except socket.error as e:
            log.error("Unable to start endpoint: ", e)
            return False

    def register(self, conn):
        """Adds `conn' to list of connections."""
        with self._lock:
            self._connections[conn.peer] = conn

    def replace(self, conn, newconn):
        """Replace `conn' with `newconn'."""
        with self._lock:
            del self._connections[conn.peer]
            self._connections[newconn.peer] = newconn

    def get_connection(self, pid):
        with self._lock:
            if pid in self._connections:
                return self._connections[pid]
            else:
                return None

    def deregister(self, conn):
        """Removes `conn' from list of connections."""
        with self._lock:
            del self._connections[conn.peer]

    def send(self, data, target, timestamp = 0):
        pass

    def recv(self, block, timeout = None):
        pass

    def recvmesgs(self):
        try:
            while True:
                r, _, _ = select.select(self._connections.keys(), [], [])

                if self._conn in r:
                    # We have pending new connections, handle the first in
                    # line. If there are any more they will have to wait until
                    # the next iteration
                    conn, addr = self._conn.accept()
                    TcpEndPoint.receivers[conn] = addr
                    r.remove(self._conn)

                for c in r:
                    try:
                        bytedata = self._receive_1(INTEGER_BYTES, c)
                        datalen = int.from_bytes(bytedata, sys.byteorder)

                        bytedata = self._receive_1(datalen, c)
                        src, tstamp, data = pickle.loads(bytedata)
                        bytedata = None

                        if not isinstance(src, EndPoint):
                            raise TypeError()
                        else:
                            yield (src, tstamp, data)

                    except pickle.UnpicklingError as e:
                        self._log.warn("UnpicklingError, packet from %s dropped",
                                       TcpEndPoint.receivers[c])

                    except socket.error as e:
                        self._log.debug("Remote connection %s terminated.",
                                        str(c))
                        del TcpEndPoint.receivers[c]

        except select.error as e:
            self._log.debug("select.error occured, terminating receive loop.")

    def getlogname(self):
        if self._address is not None:
            return "%s_%s" % (self._address[0], str(self._address[1]))
        else:
            return self._name

    def close(self):
        pass

    def __str__(self):
        if self._address is not None:
            return str(self._address)
        else:
            return self._name

    def __repr__(self):
        if self._proctype is not None:
            return "<" + self._proctype.__name__ + str(self) + ">"
        else:
            return "<process " + str(self) + ">"


# TCP Implementation:

MAX_TCP_CONN = 200
MIN_TCP_PORT = 10000
MAX_TCP_PORT = 40000
MAX_UDP_BUFSIZE = 20000
MAX_TCP_BUFSIZE = 200000          # Maximum pickled message size
MAX_RETRY = 5

class TcpEndPoint(EndPoint):
    """Endpoint based on TCP.

    """

    senders = None
    receivers = None

    def __init__(self, name=None, proctype=None, port=None):
        super().__init__(name, proctype)

        TcpEndPoint.receivers = dict()
        TcpEndPoint.senders = LRU(MAX_TCP_CONN)

        self._conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if port is None:
            while True:
                self._address = (self._name,
                                 random.randint(MIN_TCP_PORT, MAX_TCP_PORT))
                try:
                    self._conn.bind(self._address)
                    break
                except socket.error:
                    pass
        else:
            self._address = (self._name, port)
            self._conn.bind(self._address)

        self._conn.listen(10)
        TcpEndPoint.receivers[self._conn] = self._address

        self._log = logging.getLogger("runtime.TcpEndPoint(%s)" %
                                      super().getlogname())
        self._log.debug("TcpEndPoint %s initialization complete",
                        str(self._address))

    def send(self, data, src, timestamp = 0):
        retry = 1
        while True:
            conn = TcpEndPoint.senders.get(self)
            if conn is None:
                conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    conn.connect(self._address)
                    TcpEndPoint.senders[self] = conn
                except socket.error:
                    self._log.debug("Can not connect to %s. Peer is down.",
                                   str(self._address))
                    return False

            bytedata = pickle.dumps((src, timestamp, data))
            l = len(bytedata)
            header = int(l).to_bytes(INTEGER_BYTES, sys.byteorder)
            mesg = header + bytedata

            if len(mesg) > MAX_TCP_BUFSIZE:
                self._log.warn("Packet size exceeded maximum buffer size! "
                               "Outgoing packet dropped.")
                self._log.debug("Dropped packet: %s",
                                str((src, timestamp, data)))
                break

            else:
                try:
                    if self._send_1(mesg, conn):
                        break
                except socket.error as e:
                    pass
                self._log.debug("Error sending packet, retrying.")
                retry += 1
                if retry > MAX_RETRY:
                    self._log.debug("Max retry count reached, reconnecting.")
                    conn.close()
                    del TcpEndPoint.senders[self]
                    retry = 1

        self._log.debug("Sent packet %r to %r." % (data, self))
        return True

    def _send_1(self, data, conn):
        msglen = len(data)
        totalsent = 0
        while totalsent < msglen:
            sent = conn.send(data[totalsent:])
            if sent == 0:
                return False
            totalsent += sent
        return True


    def _receive_1(self, totallen, conn):
        msg = bytes()
        while len(msg) < totallen:
            chunk = conn.recv(totallen-len(msg))
            if len(chunk) == 0:
                raise socket.error("EOF received")
            msg += chunk
        return msg

    def close(self):
        pass

    def _udp_init(self, name=None, proctype=None, port=None):
        self._udpsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if port is None:
            while True:
                self._address = (self._name,
                                 random.randint(MIN_UDP_PORT, MAX_UDP_PORT))
                try:
                    self._udpsock.bind(self._address)
                    break
                except socket.error:
                    pass
        else:
            self._address = (self._name, port)
            self._udpsock.bind(self._address)

        log.debug("UdpEndPoint %s initialization complete", str(self._address))

    def send(self, data, tgt, timestamp = 0):
        bytedata = pickle.dumps((self._pid, timestamp, data))
        if len(bytedata) > MAX_UDP_BUFSIZE:
            log.warn("Data size exceeded maximum buffer size! "
                     "Outgoing packet dropped.")
            log.debug("Dropped packet: %s", str(bytedata))

        elif (self._udpsock.sendto(bytedata, self._address) !=
              len(bytedata)):
            raise socket.error()

    def recvmesgs(self):
        flags = 0

        try:
            while True:
                bytedata = self._udpsock.recv(MAX_UDP_BUFSIZE, flags)
                src, tstamp, data = pickle.loads(bytedata)
                if not isinstance(src, EndPoint):
                    raise TypeError()
                else:
                    yield (src, tstamp, data)
        except socket.error as e:
            self._log.debug("socket.error occured, terminating receive loop.")

