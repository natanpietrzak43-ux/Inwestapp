"""Optional owner-configured SMTP alarm channel; no credentials in API output."""
from email.message import EmailMessage
from email.utils import parseaddr
import os
import smtplib
import ssl
from user_data import data_dir
import secure_store


def settings():
    try:return secure_store.read(data_dir()/'private'/'alerts.json')
    except (OSError,ValueError):return None


def validate(cfg):
    if not isinstance(cfg,dict) or not all(isinstance(cfg.get(k),str) and cfg[k].strip() for k in ('host','username','password','recipient','sender')):raise ValueError('Niepełna konfiguracja poczty alarmowej.')
    if any('\n' in cfg[k] or '\r' in cfg[k] for k in ('host','username','recipient','sender')):raise ValueError('Nieprawidłowe pola poczty alarmowej.')
    if cfg.get('port') not in (465,587):raise ValueError('SMTP: wybierz port 465 (TLS) albo 587 (STARTTLS).')
    for key in ('recipient','sender'):
        if parseaddr(cfg[key])[1]!=cfg[key] or '@' not in cfg[key]:raise ValueError('Wymagany pojedynczy adres e-mail.')
    return cfg


def configured():
    try:validate(settings());return True
    except ValueError:return False


def send(event):
    cfg=validate(settings());message=EmailMessage()
    message['From']=cfg['sender'];message['To']=cfg['recipient'];message['Subject']='Inwestapp: '+event['kind']
    message['Message-ID']='<'+event['eventId']+'@inwestapp.local>'
    message.set_content(event['at']+'\n'+event['scope']+'\n'+event['message'])
    context=ssl.create_default_context()
    if cfg['port']==465:
        with smtplib.SMTP_SSL(cfg['host'],cfg['port'],timeout=8,context=context) as smtp:
            smtp.login(cfg['username'],cfg['password']);smtp.send_message(message)
    else:
        with smtplib.SMTP(cfg['host'],cfg['port'],timeout=8) as smtp:
            smtp.ehlo();smtp.starttls(context=context);smtp.ehlo();smtp.login(cfg['username'],cfg['password']);smtp.send_message(message)
