#!/usr/bin/env python

def callback(server,msg):
    print('Received message from {0}'.format(msg['From']))
