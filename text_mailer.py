#!/usr/bin/python

# Author: Troy W. Caro <twc17@pitt.edu>
# Version: 1.0.0
# Last Modified: <10/19/2017>
#
# Purpose:
#   Easy way to send text files via email. Doing this to easily call from other scripts
#   so that the from, to, subject, body, attachment can be switched out easily.
#
# Dependencies:
#   python version 2.6+
#
# Usage:
#   

# Imports
import os
import sys
import argparse
import smtplib

# Packages
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_mail(toaddr, fromaddr, subject, body, filename):
    # Time to build the email
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = fromaddr
    msg['To'] = toaddr

    msg.attach(MIMEText(body, 'plain'))

    attachment = open(filename, 'r')

    part = MIMEText(attachment.read())
    part.add_header('Content-Disposition', "attachment", filename=filename)
    
    msg.attach(part)

    server = smtplib.SMTP('smtp.pitt.edu', 25)
    text = msg.as_string()

    # Try to send it!
    try:
        server.sendmail(fromaddr, toaddr, text)
        server.quit()
    except Exception as e:
            print(e)
    attachment.close()
