#!/usr/bin/env python

def acknowledge(server,msg,body):
    print 'Received message from {0}'.format(msg['From'])

def respond(server,msg,body):
    server.send(msg['From'],body=body)
    print 'Replied'

def note(server,msg,body):
    if msg['From']=='asdf@vtext.com' and body.lower().startswith('note'):
        with open('notes.txt','a') as f:
            f.write(body[4:].strip()+'\n')

allfuncs = [acknowledge,note,respond]
