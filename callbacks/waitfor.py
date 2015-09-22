#!/usr/bin/env python

from time import sleep
import sys

def callback(server,msg):
    text = msg['Body'].split()
    if text[0].lower() == 'wait':
        seconds = int(text[1])
        print('Waiting for {} seconds'.format(seconds))
        for i in range(int(seconds)):
            print('\r{}/{}     '.format(i,seconds),end='')
            sys.stdout.flush()
            sleep(1)
        print('\r{}/{}     '.format(seconds,seconds))
        print('Done waiting')

        return True
