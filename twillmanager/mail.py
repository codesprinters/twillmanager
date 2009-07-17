# encoding: utf-8

from email.MIMEText import MIMEText
import os
import smtplib

class Mailer(object):
    def __init__(self, config):
        self.config = config

    def send_mail(self, sender, recipients, subject, body):
        raise NotImplementedError()

    def _make_message(self, sender, recipients, subject, body):
        """ Makes a message string """
        recipients = [r.encode('utf-8') for r in recipients]
        msg = MIMEText(body)
        msg['Subject'] = subject.encode('utf-8')
        msg['From'] = sender.encode('utf-8')
        msg['To'] = ", ".join(recipients)
        return msg.as_string()

class SMTPMailer(Mailer):
    def send_mail(self, sender, recipients, subject, body):
        msg = self._make_message(sender, recipients, subject, body)

        login = self.config.get('mail.smtp.login', None)
        password = self.config.get('mail.smtp.password', None)
        usetls = self.config.get('mail.smtp.usetls', False)

        server = smtplib.SMTP(self.config['mail.smtp.server'], self.config['mail.smtp.port'])
        server.ehlo()
        if usetls:
            server.starttls()
            server.ehlo()
        
        if login:
            server.login(login, password)

        server.sendmail(sender.encode('utf-8'), [r.encode('utf-8') for r in recipients], msg)
        server.close()

class SendmailMailer(Mailer):
    def send_mail(self, sender, recipients, subject, body):
        msg = self._make_message(sender, recipients, subject, body)
        p = os.popen("%s -t" % self.config.get("mail.sendmail.command", '/usr/bin/sendmail'), 'w')
        p.write(msg)
        p.close()


def create_mailer(config):
    mode = config['mail.mode']

    if mode == 'smtplib' or mode == 'smtp':
        return SMTPMailer(config)
    elif mode == 'sendmail':
        return SendmailMailer(config)
    else:
        raise RuntimeError("Invalid mailer mode: %s" % mode)