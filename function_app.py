import logging
import azure.functions as func
import feedparser
import pandas
from datetime import datetime
import time
import os
from azure.storage.blob import BlobServiceClient
from io import StringIO


app = func.FunctionApp()

@app.schedule(schedule="0 0 13 * * *", arg_name="myTimer", run_on_startup=True, use_monitor=False) 
def timer_trigger(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('The timer is past due!')

    connection_string = os.getenv("STORAGEACCOUNT_CONNECTIONSTRING")

    urls = []
    with open("feeds.txt", "r") as f:
        for line in f:
            urls.append(line)


    feeds = {"Source": [], "Title": [], "Description": [], "Link": []}
    for url in urls:
        feed = feedparser.parse(url)
        feedTitle = feed.feed.title
        i = 0
        while i < len(feed.entries):
            t1 = datetime.now()
            t2 = datetime.fromtimestamp(time.mktime(feed.entries[i].published_parsed))
            if (t1 - t2).days < 1:
                feeds["Source"].append(feedTitle)
                feeds["Title"].append(feed.entries[i].title)
                feeds["Description"].append((str(feed.entries[i].description).encode("utf-8"))[:150])
                feeds["Link"].append(feed.entries[i].link)
            i = i + 1

    df = pandas.DataFrame(data=feeds)
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)

    # Set up your connection string, container name, and blob name
    container_name = "func-output"
    blob_name = "feed.csv"

    # Initialize the BlobServiceClient
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)

    # Get the container client
    container_client = blob_service_client.get_container_client(container_name)

    # Get the BlobClient to upload the file
    blob_client = container_client.get_blob_client(blob_name)

    # Upload the file
    blob_client.upload_blob(csv_buffer.getvalue(), overwrite=True)

    logging.info('Python timer trigger function executed.')