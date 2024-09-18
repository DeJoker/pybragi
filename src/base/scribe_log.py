from scribe import scribe
from thrift.transport import TTransport, TSocket
from thrift.protocol import TBinaryProtocol
from logging import StreamHandler
import sys

# 日志收集
class ScribeHandler(StreamHandler):
    """
    A handler class which writes formatted logging records to Scrbie Server
    """
    client = None

    def __init__(self, host='127.0.0.1', port=1464, category=None, delay=0):
        """
        Open the specified file and use it as the stream for logging.
        """
        if category is None:
            category = 'root'
        self.host = host
        self.port = port
        self.category = category
        if delay:
            self.stream = None
        else:
            stream = self._open()
            StreamHandler.__init__(self, stream)

    def close(self):
        """
        Closes the stream.
        """
        if self.stream:
            self.flush()
            if hasattr(self.stream, "close"):
                self.stream.close()
            StreamHandler.close(self)
            self.stream = None

    def _open(self):
        """
        Open the current base file with the (original) mode and encoding.
        Return the resulting stream.
        """
        try:
            socket = TSocket.TSocket(host=self.host, port=self.port)
            transport = TTransport.TFramedTransport(socket)
            protocol = TBinaryProtocol.TBinaryProtocol(trans=transport, strictRead=False, strictWrite=False)
            self.client = scribe.Client(iprot=protocol, oprot=protocol)
            transport.open()
        except Exception as e:
            print (e)
            return None
        return transport

    def emit(self, record):
        """
        Emit a record.

        If the stream was not opened because 'delay' was specified in the
        constructor, open it before calling the superclass's emit.
        """
        if self.stream is None:
            stream = self._open()
            StreamHandler.__init__(self, stream)
        self.record(record)

    def record(self, record):
        """
        Emit a record.

        If a formatter is specified, it is used to format the record.
        The record is then written to the stream with a trailing newline.  If
        exception information is present, it is formatted using
        traceback.print_exception and appended to the stream.  If the stream
        has an 'encoding' attribute, it is used to encode the message before
        output to the stream.
        """
        try:
            msg = self.format(record)
            import socket
            log_entry = scribe.LogEntry(category=self.category, message='[%s]%s' % (socket.gethostname(), msg))
            if self.client is not None:
                result = self.client.Log(messages=[log_entry])
                if result == scribe.ResultCode.TRY_LATER:
                    sys.stderr.write("TRY_LATE")
        except (KeyboardInterrupt, SystemExit):
            raise
        except IOError as e:
            import errno
            if e.errno == errno.EPIPE:
                pass
            else:
                self.handleError(record)
        except:
            self.handleError(record)
