#!/usr/bin/env python

def callback(server,msg):
    server.send(msg['From'],body=msg['Body'])
    print 'Replied'
    return True
