#!/usr/bin/python3

from smtp import SMTP
import sys

if __name__ == '__main__':
    from_addr = input('From: ')
    to_addrs = input('To: ').split(',')
    print('Enter message:')
    msg = ''
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        msg += line

    client = SMTP('localhost')
    client.set_debug(True)
    client.sendmail(from_addr, to_addrs, msg)
    client.quit()
