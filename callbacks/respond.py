#!/usr/bin/env python

def callback(server,msg):
    if 'gmail' in msg['From']:
        server.send(msg['From'],body=msg['Body'])
        print('Replied')
