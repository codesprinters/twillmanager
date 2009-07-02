# encoding: utf-8

from email.MIMEText import MIMEText
import smtplib

class Mailer(object):
    def __init__(self, config):
        self.config = config

    def send_mail(self, sender, recipients, subject, body):
        raise NotImplementedError()


class SMTPMailer(Mailer):
    def send_mail(self, sender, recipients, subject, body):
        recipients = [r.encode('utf-8') for r in recipients]

        msg = MIMEText(body)
        msg['Subject'] = subject.encode('utf-8')
        msg['From'] = sender.encode('utf-8')
        msg['To'] = ", ".join(recipients)

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

        server.sendmail(sender.encode('utf-8'), recipients, msg.as_string())
        server.close()

def create_mailer(config):
    mode = config['mail.mode']

    if mode == 'smtplib':
        return SMTPMailer(config)
    elif mode == 'sendmail':
        return SendmailMailer(config)
    else:
        raise RuntimeError("Invalid mailer mode: %s" % mode)