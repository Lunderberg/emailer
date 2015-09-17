#!/usr/bin/env python

def callback(server,msg):
    if msg['From']=='asdf@vtext.com' and msg['Body'].lower().startswith('note'):
        with open('notes.txt','a') as f:
            f.write(body[4:].strip()+'\n')
