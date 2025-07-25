import logging
import azure.functions as func
from datetime import datetime, timezone
import os
from io import StringIO
import smtplib
from email.mime.text import MIMEText
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
import urllib.request
import xml.etree.ElementTree as ET
import csv


# TODO:
# -add link to inactive feeds' blogs 


app = func.FunctionApp()

timezones = {
    "PDT": "-0700",
    "PST": "-0800",
    "GMT": "+0000",
    }

@app.schedule(schedule="0 0 12 * * 1", arg_name="myTimer", run_on_startup=False, use_monitor=False) 
def timer_trigger(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('The timer is past due!')

    inputFeeds = []
    with open("feeds.txt", "r") as f:
        for line in f:
            inputFeeds.append(line)

    # loop through all feeds
    feeds = {"Source": [], "Date": [], "Title": [], "Description": [], "Link": []}
    for inputFeed in inputFeeds:
        
        url, feedTitle = inputFeed.split(",")[0], inputFeed.split(",")[1]

        # set user agent to Mozilla to avoid getting blocked by some sites - two methods
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (platform; rv:17.0) Gecko/20100101 Firefox/17.0'})
            xml_data = urllib.request.urlopen(req).read()
        except urllib.error.HTTPError:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            xml_data = urllib.request.urlopen(req).read()

        # read xml data
        feed = ET.fromstring(xml_data).find('channel')

        # loop through all items in the feed
        for item in feed.findall('item'):

            # convert and compare timestamps
            t1 = datetime.now().astimezone(timezone.utc)
            # ISO 8601 -> datetime
            try:
                if item.find('pubDate').text[-1:] == "Z": 
                    t2 = datetime.strptime(item.find('pubDate').text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                # RFC 1123 -> datetime
                elif item.find('pubDate').text[-1:].isalpha(): 
                    t2 = item.find('pubDate').text[:-3] + timezones[item.find('pubDate').text[-3:]]
                    t2 = datetime.strptime(t2, "%a, %d %b %Y %H:%M:%S %z").astimezone(timezone.utc)
                # RFC 2822 -> datetime
                else:
                    t2 = datetime.strptime(item.find('pubDate').text, "%a, %d %b %Y %H:%M:%S %z").astimezone(timezone.utc)
            except ValueError:
                try:
                    t2 = datetime.strptime(item.find('pubDate').text, "%a, %d %b %y %H:%M:%S %z").astimezone(timezone.utc)
                except ValueError:
                    # format: Jun 05, 2025 00:00:00-0500
                    t2 = datetime.strptime(item.find('pubDate').text, "%b %d, %Y %H:%M:%S%z").astimezone(timezone.utc)
            if ((t1 - t2).days) <= 7:
                feeds["Source"].append(feedTitle.lstrip('\n').lstrip(" "))
                feeds["Date"].append(item.find('pubDate').text)
                feeds["Title"].append(item.find('title').text)
                feeds["Link"].append(item.find('link').text.lstrip('\n').lstrip(" ")) # clean up link field - messy on some RSS feeds
                if item.find('description') is not None:
                    feeds["Description"].append((str(item.find('description').text).encode("utf-8"))[:150])
                else:
                    feeds["Description"].append("N/A")

    # write csv data to buffer
    csv_buffer = StringIO()
    keys = feeds.keys()
    writer = csv.writer(csv_buffer)
    writer.writerow(keys)
    writer.writerows(zip(*feeds.values()))

    # send email
    subject = "Weekly SOC RSS Feed"
    body = "Attached is your weekly SOC RSS Feed."
    recipient_email = os.getenv("RECIPIENTS").split(" ")
    sender_email = os.getenv("SENDER")
    sender_password = os.getenv("APP_PASSWORD")

    file_part = MIMEBase("application", "octet-stream")
    file_part.set_payload(csv_buffer.getvalue())
    encoders.encode_base64(file_part)
    file_part.add_header("Content-Disposition", "attachment; filename = feed.csv")

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = ', '.join(recipient_email)
    msg['Subject'] = subject
    body_part = MIMEText(body)
    msg.attach(file_part)
    msg.attach(body_part)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
        smtp_server.login(sender_email, sender_password)
        smtp_server.sendmail(sender_email, recipient_email, msg.as_string())

    # close csv buffer
    csv_buffer.close()

    logging.info('Python timer trigger function executed.')
