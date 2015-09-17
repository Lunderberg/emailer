#!/usr/bin/env python

import smtplib
from imapclient import IMAPClient
import email
import threading


class Server(object):
    def __init__(self,username,password,callback):
        self.username = username
        self.password = password
        self.callback = callback
        self.noop_period = 60*10

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, value, traceback):
        self.stop()

    def start(self):
        self.imap_poll = self.imap_connect()
        self.imap_idle = self.imap_connect()
        self.smtp = self.smtp_connect()

        self.firstCalling = True
        self.stop_running = threading.Event()
        self.has_mail = threading.Event()

        self.keepalive_thread = threading.Thread(target=self._keepalive)
        self.keepalive_thread.start()
        self.idle_thread = threading.Thread(target=self._idle)
        self.idle_thread.start()
        self.poll_thread = threading.Thread(target=self._poll)
        self.poll_thread.start()

    def stop(self):
        self.stop_running.set()
        self.keepalive_thread.join()
        self.idle_thread.join()
        self.poll_thread.join()

    def wait(self):
        while not self.stop_running.wait(1):
            pass

    def _keepalive(self):
        while not self.stop_running.is_set():
            for i in range(self.noop_period):
                if self.stop_running.wait(1):
                    return
            self.noop()

    def _idle(self):
        while not self.stop_running.is_set():

            self.imap_idle.idle()

            for i in range(self.noop_period):
                if self.imap_idle.idle_check(1):
                    self.has_mail.set()
                if self.stop_running.is_set():
                    return

            self.imap_idle.idle_done()
            self.imap_idle.noop()

    def _poll(self):
        self.process_unread()

        while not self.stop_running.is_set():
            while True:
                if self.has_mail.wait(1):
                    self.has_mail.clear()
                    break
                elif self.stop_running.is_set():
                    return

            self.process_unread()

    def imap_connect(self):
        imap = IMAPClient('imap.gmail.com',use_uid=True,ssl=True)
        imap.login(self.username,self.password)
        imap.select_folder('INBOX')
        return imap

    def smtp_connect(self):
        smtp = smtplib.SMTP('smtp.gmail.com',587)
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(self.username,self.password)
        return smtp

    def noop(self):
        self.smtp.noop()
        self.imap_poll.noop()

    def send(self,recipient,subject='',body=''):
        headers = ['from: ' + self.username,
                   'subject: ' + subject,
                   'to: ' + recipient,
                   'mime-version: 1.0',
                   'content-type: text/html']
        headers = '\r\n'.join(headers)
        self.smtp.sendmail(self.username,recipient,headers+'\r\n\r\n'+body)

    def gmail_search(self,searchstring):
        return self.imap_poll.search(['X-GM-RAW "{0}"'.format(searchstring)])

    def archive(self,messages):
        self.imap_poll.copy(messages,'[Gmail]/All Mail')
        self.imap_poll.delete_messages(messages)

    def get_unread(self):
        conditions = ['!label:handled-done','!label:handled-error']
        if self.firstCalling:
            self.firstCalling = False
        else:
            conditions.append('!label:read-unhandled')
        self.imap_poll.select_folder('INBOX')
        messages = self.gmail_search(' AND '.join(conditions))
        response = self.imap_poll.fetch(messages,['RFC822'])
        msgs = [(msgid,email.message_from_string(data['RFC822']))
                for msgid,data in response.iteritems()]
        self.imap_poll.set_gmail_labels(messages,['read-unhandled'])
        return msgs

    def unpack_body(self, message):
        for part in message.walk():
            if part.get_content_type()=='text/plain':
                return part.get_payload()
        return ''

    def process_unread(self):
        id_succeed = []
        id_fail = []
        for msgid,msg in self.get_unread():
            success = self.callback(self,msg,self.unpack_body(msg))
            (id_succeed if success else id_fail).append(msgid)
        if id_succeed:
            self.imap_poll.set_gmail_labels(id_succeed,['handled-done'])
            self.archive(id_succeed)
        if id_fail:
            self.imap_poll.set_gmail_labels(id_fail,['handled-error'])


from callbacks import allfuncs
def callback(server,msg):
    for part in msg.walk():
        if part.get_content_type()=='text/plain':
            body = part.get_payload()

    results = [func(server,msg,body) for func in allfuncs]
    return any(results)

if __name__=='__main__':
    username,password = [line.strip() for line in open('config.txt')][:2]
    with Server(username, password, callback) as s:
        s.wait()
