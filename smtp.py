import socket
import re

CRLF = '\r\n'
bCRLF = b'\r\n'


class SMTP:
    DEFAULT_PORT = 25
    is_debug = False
    sock = None
    file = None
    helo_response = None

    def __init__(self, host='', port=0, is_debug=False):
        self.host = host
        self.is_debug = is_debug

        if host:
            (code, msg) = self.connect(host, port)
            if code != 220:
                raise OSError('SMTP connection error')

    def set_debug(self, is_debug):
        self.is_debug = is_debug

    def connect(self, host='localhost', port=0):
        if not port and (host.find(':') == host.rfind(':')):
            i = host.rfind(':')
            if i >= 0:
                host, port = host[:i], host[i + 1:]
                port = int(port)
        if not port:
            port = SMTP.DEFAULT_PORT

        self.sock = self._create_socket(host, port)
        self.file = None
        (code, msg) = self.getreply()

        if self.is_debug:
            print('connected: {}'.format(msg))

        return code, msg

    @staticmethod
    def _create_socket(host, port):
        return socket.create_connection((host, port))

    def getreply(self):
        response = []
        code = -1
        if self.file is None:
            self.file = self.sock.makefile('r')
        while True:
            try:
                line = self.file.readline()
            except OSError:
                self.close()
                raise

            if not line:
                self.close()
                raise OSError('Connection unexpectedly closed.')

            response.append(line[4:].strip(' \t\r\n'))
            code = line[:3]

            try:
                code = int(code)
            except ValueError:
                code = -1
                break

            if line[3] != '-':
                break

        msg = '\n'.join(response)
        if self.is_debug:
            print('reply: \n\tcode: {} \n\tmsg: {}'.format(code, msg))

        return code, msg

    def send(self, s):
        if self.is_debug:
            print('send: {}'.format(s))

        if self.sock:
            if isinstance(s, str):
                s = s.encode('ascii')

            try:
                self.sock.sendall(s)
            except OSError as e:
                self.close()
                raise OSError('Unable to send {}'.format(e))
        else:
            raise OSError('Not connected, run connect() first')

    def perform_cmd(self, cmd, args=''):
        if not args:
            s = '{}{}'.format(cmd, CRLF)
        else:
            s = '{} {}{}'.format(cmd, args, CRLF)
        self.send(s)
        return self.getreply()

    def helo(self):
        (code, msg) = self.perform_cmd('helo')
        self.helo_response = msg

    def rset(self):
        return self.perform_cmd('rset')

    def noop(self):
        return self.perform_cmd('noop')

    @staticmethod
    def _quote_address(address: str):
        if address.startswith('<'):
            return address
        else:
            return '<{}>'.format(address)

    @staticmethod
    def _quote_periods(msg):
        return re.sub(br'(?m)^\.', b'..', msg)

    def mail(self, recipient):
        return self.perform_cmd('mail', 'FROM:{}'.format(SMTP._quote_address(recipient)))

    def rcpt(self, recipient):
        return self.perform_cmd('rcpt', 'TO:{}'.format(SMTP._quote_address(recipient)))

    def data(self, msg):
        (code, response) = self.perform_cmd('data')
        if code != 354:
            raise OSError("Cant't send data: {}".format(response))
        else:
            if isinstance(msg, str):
                msg = msg.encode('ascii')
            msg = SMTP._quote_periods(msg)
            if msg[-2:] != bCRLF:
                msg += bCRLF
            msg += b'.' + bCRLF
            self.send(msg)
            (code, resp) = self.getreply()
            return code, resp

    def close(self):
        try:
            if self.file:
                self.file.close()
            self.file = None
        finally:
            if self.sock:
                self.sock.close()
                self.sock = None

    def quit(self):
        response = self.perform_cmd('quit')
        self.helo_response = None
        self.close()
        return response

    def sendmail(self, from_addr, to_addrs, msg):
        self.helo()

        if isinstance(msg, str):
            msg = msg.encode('ascii')

        (code, response) = self.mail(from_addr)
        if code != 250:
            self.close()
            raise OSError('Unable to send: {}, {}'.format(code, response))
        recipients_errors = {}
        if isinstance(to_addrs, str):
            to_addrs = [to_addrs]
        for addr in to_addrs:
            (code, response) = self.rcpt(addr)
            if (code != 250) and (code != 251):
                recipients_errors[addr] = (code, response)
            if code == 421:
                self.close()
                raise OSError('Recipient refused: {} {} {}'.format(addr, code, response))

        if len(recipients_errors) == len(to_addrs):
            # the server refused all our recipients
            self.rset()
            raise OSError('All recipients refused.')
        (code, response) = self.data(msg)
        if code != 250:
            raise OSError('Unable to send.')
        return recipients_errors
