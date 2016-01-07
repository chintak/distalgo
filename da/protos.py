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
import socket
import random
import pickle

INTEGER_BYTES = 8

class Connection:
    """Represents a connection to a remote peer.

    """
    def __init__(self, sock, addr, proto):
        self.sock = sock
        self.peer = addr
        self.proto = proto

    def fileno(self):
        return self.sock.fileno()

    def close(self):
        self.sock.close()

class PendingConnection:
    """Placeholder for a TCP socket before full protocol negotiation completes.

    """
    def __init__(self, sock, addr, proto):
        super().__init__(sock, addr, proto)


class Protocol:
    """Defines a lower level transport protocol.

    """
    max_retries = 5
    min_port = 10000
    max_port = 65535

    def __init__(self, endpoint, port=None):
        self._ep = endpoint
        self.port = port

        self._log = logging.getLogger(self.__class__.__name__)

    def start(self):
        """Starts the protocol.

        For wrapper protocols this creates and binds the lower level sockets.

        """
        pass

    def send(self, msg, conn=None):
        """Send `msg' through `conn'.

        Returns `True' if send succeeded, `False' otherwise.

        """
        return False

    def recv(self, conn):
        """Receives a message on `conn'.

        """
        return None

class TcpProtocol(Protocol):
    def __init__(self, endpoint, port=None):
        super().__init__(endpoint, port)

    def start(self):
        """Starts the TCP listener socket.

        """

        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if self.port is None:
            done = False
            for _ in range(Protocol.max_retries):
                self.port = random.randint(Protocol.min_port, Protocol.max_port)
                try:
                    self.listener.bind((self._ep.hostname, self.port))
                    done = True
                    break
                except socket.error:
                    pass
            if not done:
                self.listener.close()
                raise socket.error("Unable to bind to free port.")
        else:
            self.listener.bind((self._ep.hostname, self.port))

    def _accept(self):
        sock, addr = self.listener.accept()
        conn = PendingConnection(sock, addr, self)
        self._ep.register(conn)

    def recv(self, conn):
        """Handles incoming data over `conn'."""

        if conn.sock is self.listener:
            self._accept()
        else:
            try:
                bytedata = self._receive_1(INTEGER_BYTES, conn.sock)
                datalen = int.from_bytes(bytedata, sys.byteorder)
                bytedata = self._receive_1(datalen, conn.sock)
                if isinstance(conn, PendingConnection):
                    peerid, tstamp, data = pickle.loads(bytedata)
                    bytedata = None
                    newconn = Connection(conn.sock, peerid, self)
                    self._ep.replate(conn, newconn)
                    yield (peerid, tstamp, data)
                else:
                    tstamp, data = pickle.loads(bytedata)
                    bytedata = None
                    yield (conn.peer, tstamp, data)

            except pickle.UnpicklingError as e:
                self._log.warn("UnpicklingError, packet from %s dropped",
                               TcpEndPoint.receivers[c])
            except socket.error as e:
                self._log.debug("Remote connection %s terminated.",
                                str(c))
                self._ep.deregister(conn)

    def _receive_1(self, totallen, conn):
        """Helper function to receive `totallen' number of bytes over
        `conn'. 

        """
        msg = bytearray(totallen)
        offset = 0
        while offset < totallen:
            recvd = conn.recv_into(memoryview(msg)[offset:])
            if recvd == 0:
                raise socket.error("EOF received")
            offset += recvd
        return msg

    def send(self, data, dest, timestamp=0):
        """Sends `data' to `dest'. """
        retry = 1
        buffer = io.BytesIO(b'0' * INTEGER_BYTES)
        for _ in range(Protocol.max_retries):
            conn = self._ep.get_connection(dest)
            if conn is None:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    sock.connect(self._ep.decode(dest, self))
                except socket.error:
                    self._log.debug("Can not connect to %s. Peer is down.",
                                   str(self._address))
                    return False
                conn = Connection(sock, dest, self)
                self._ep.register(conn)
                bytedata = pickle.dumps((self._ep.pid, timestamp, data))
            else:
                bytedata = pickle.dumps((timestamp, data))

            l = len(bytedata)
            header = int(l).to_bytes(INTEGER_BYTES, sys.byteorder)
            mesg = header + bytedata

            if len(mesg) > MAX_TCP_BUFSIZE:
                self._log.warn("Packet size exceeded maximum buffer size! "
                               "Outgoing packet dropped.")
                self._log.debug("Dropped packet: %s",
                                str((src, timestamp, data)))
                return False

            else:
                try:
                    conn.sendall(mesg)
                    self._log.debug("Sent packet %r to %r." % (data, self))
                    return True
                except socket.error as e:
                    pass
                self._log.debug("Error sending packet, retrying.")
                retry += 1
                if retry > MAX_RETRY:
                    self._log.debug("Max send retry count reached, "
                                    "attempting to reconnecting...")
                    conn.close()
                    self._ep.deregister(conn, self)
                    retry = 1

        return False

class ProtocolSuite:
    """A bundle of network protocols.

    Each process in the same instance of distributed program must have the
    same ProtocolSuite.
    """
    def __init__(self, endpoint):
        self._ep = endpoint
        self.protocols = []

    def start(self):
        pass

class TcpUdpSuite(ProtocolSuite):
    def __init__(self, endpoint):
        super().__init__(endpoint)
        self.tcpproto = None
        self.udpproto = None

    def start(self):
        self.tcpproto = TcpProtocol(self._ep)
        self.udpproto = UdpProtocol(self._ep)
        tcpport = tcp.start(self)
        udpport = udp.start(self)

    # TODO: We use a namedtuple for simplicity, but needs to be changed if we
    # are to support process migration:
    class ProcessId(namedtuple('ProcessId',
                               'udpport, tcpport, nodeport, ipaddr')):
        """Object representing a process id.

        """
        @property
        def tcp_addr(self):
            ipaddr = ipaddress.ip_address(self.ipaddr)
            return (str(ipaddr), self.tcpport)

        @property
        def udp_addr(self):
            ipaddr = ipaddress.ip_address(self.ipaddr)
            return (str(ipaddr), self.udpport)

