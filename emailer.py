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
        self.imap = self.imap_connect()

        self.firstCalling = True
        self.stop_running = threading.Event()
        self.has_mail = threading.Event()

        self.idle_thread = threading.Thread(target=self._idle)
        self.idle_thread.start()

        print('Listening for messages now')

    def stop(self):
        self.stop_running.set()
        self.idle_thread.join()

    def wait(self):
        while not self.stop_running.wait(1):
            pass

    def _idle(self):
        while not self.stop_running.is_set():

            self.imap.idle()

            has_mail = False
            for i in range(self.noop_period):
                if self.imap.idle_check(1):
                    has_mail = True
                    break
                if self.stop_running.is_set():
                    return

            self.imap.idle_done()

            if has_mail:
                while self.process_unread():
                    pass

            self.imap.noop()

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

    def send(self,recipient,subject='',body=''):
        headers = ['from: ' + self.username,
                   'subject: ' + subject,
                   'to: ' + recipient,
                   'mime-version: 1.0',
                   'content-type: text/html']
        headers = '\r\n'.join(headers)
        self.smtp_connect().sendmail(self.username,recipient,headers+'\r\n\r\n'+body)

    def gmail_search(self,searchstring):
        return self.imap.search(['X-GM-RAW "{0}"'.format(searchstring)])

    def archive(self,messages):
        self.imap.copy(messages,'[Gmail]/All Mail')
        self.imap.delete_messages(messages)

    def get_unread(self):
        conditions = ['!label:handled-done','!label:handled-error']
        if self.firstCalling:
            self.firstCalling = False
        else:
            conditions.append('!label:read-unhandled')
        self.imap.select_folder('INBOX')
        messages = self.gmail_search(' AND '.join(conditions))
        response = self.imap.fetch(messages,['RFC822'])
        msgs = [(msgid,email.message_from_string(data[b'RFC822'].decode('utf-8')))
                for msgid,data in response.items()]
        self.imap.set_gmail_labels(messages,['read-unhandled'])
        return msgs

    def unpack_body(self, message):
        for part in message.walk():
            if part.get_content_type()=='text/plain':
                message['Body'] = part.get_payload()
                return
        message['Body'] = ''

    def process_unread(self):
        id_succeed = []
        id_fail = []
        messages = self.get_unread()
        for msgid,msg in messages:
            self.unpack_body(msg)
            success = self.callback(self,msg)
            (id_succeed if success else id_fail).append(msgid)
        if id_succeed:
            self.imap.set_gmail_labels(id_succeed,['handled-done'])
            self.archive(id_succeed)
        if id_fail:
            self.imap.set_gmail_labels(id_fail,['handled-error'])

        return bool(messages)


def main():
    username,password = [line.strip() for line in open('config.txt')][:2]

    import callbacks
    def callback(server,msg):
        results = [func(server,msg) for func in callbacks.callbacks]
        return any(results)

    with Server(username, password, callback) as s:
        s.wait()


if __name__=='__main__':
    main()
