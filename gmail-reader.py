from __future__ import print_function
from datetime import datetime
from datetime import timedelta
# from config import LABEL_NAME
# from config import DATABASE_FILE
# from config import CREDENTIALS_JSON
# from config import TARGET_LABEL_NAME
# from config_boj import LABEL_NAME
# from config_boj import DATABASE_FILE
# from config_boj import CREDENTIALS_JSON
# from config_boj import TARGET_LABEL_NAME
import os.path
import sqlite3

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# def create_message(sender, to, subject, message_text):
#     """
#     from email.mime.text import MIMEText
#     import base64
#     message = create_message('me', john@gmail.com, 'hello', 'testing 123')
#     """
#     message = MIMEText(message_text)
#     message['to'] = to
#     message['from'] = sender
#     message['subject'] = subject
#     return {'raw': base64.urlsafe_b64encode(message.as_string().encode()).decode()}


# def send_message(service, user_id, message):
#     """
#     print(send_message(service=service, user_id='me', message=message))
#     """
#     try:
#         message = (service.users().messages().send(userId=user_id, body=message)
#                    .execute())
#         print('Message Id: %s' % message['id'])
#         return message
#     except Exception as error:
#         print(error)

def init_db():
    # create a connection
    conn = sqlite3.connect( DATABASE_FILE )
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE email_alerts (date DATE, email TEXT, message TEXT)")
    conn.commit()
    conn.close()

def get_labels(service):
    # Call the Gmail API
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])

    return labels

def authenticate():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_JSON, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = None
    service = build('gmail', 'v1', credentials=creds)

    return service


def insert_entry(d, email, msg):
    conn = sqlite3.connect( DATABASE_FILE )
    cursor = conn.cursor()
    params = (d, email, msg)
    cursor.execute("INSERT INTO email_alerts VALUES (?,?,?)", params)
    conn.commit()
    conn.close()

def insert_multiple_entries( packed_messages ):
    conn = sqlite3.connect( DATABASE_FILE )
    cursor = conn.cursor()

    for m in packed_messages:
        params = (m[0], m[1], m[2])
        cursor.execute("INSERT INTO email_alerts VALUES (?,?,?)", params)

    conn.commit()
    conn.close()


def print_entries ( packed_messages ):
    for m in packed_messages:
        print ('%s\t%s\t%s' % (m[0], m[1], m[2]) )


def get_labels(service):
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])

    if not labels:
        print('No labels found.')
        return

    for label in labels:
        print("LABEL_NAME[\'%s\']=\'%s\'" % (label['name'], label['id']))

def get_individual_messages(service, messages_data):
    all_messages = []

    for m in messages_data:
        try:
                msg = service.users().messages().get(userId='me', id=m['id'])
                ret = msg.execute()
                date_format = "%d %b %Y %H:%M:%S %z (%Z)"
                date_str = str(ret['payload']['headers'][1]['value']).split(";")[1].lstrip()
                date_str = date_str[5:].rstrip()
                d = datetime.strptime(date_str, date_format)
                u = str(ret['snippet']).split(":")[1].lstrip()
                m = str(ret['snippet']).split(":")[0].lstrip()

                all_messages.append([d, u, m])
        except Exception as err:
            print('msg: %s' % msg)
            print('ret: %s' % ret)
            print(f"Unexpected {err=}, {type(err)=}")
            continue

    return all_messages


def get_last_database_entry():
    conn = sqlite3.connect( DATABASE_FILE )
    cursor = conn.cursor()

    last_date = cursor.execute("SELECT date FROM email_alerts GROUP BY date ORDER BY date desc LIMIT 1").fetchall()

    if last_date and len(last_date) == 1:
        return last_date[0][0]
    
    return None


def main():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """

    if not os.path.isfile( DATABASE_FILE ):
        print('Database file does not exist, initializing...')
        init_db()

    last_date_entry = get_last_database_entry()
    last_date = None
    if last_date_entry:
        last_date_entry = last_date_entry.split(' ')[0]
        date_format = "%Y-%m-%d"
        last_date = datetime.strptime(last_date_entry, date_format).date()
        last_date = last_date + timedelta(days=1)
        last_date = str(last_date).replace('-','/')

    try:
        # Authenticate with Gmail API
        service = authenticate()
        
        pageToken = None

        ################
        LABELID = LABEL_NAME[TARGET_LABEL_NAME]
        ################

        # Call the Gmail API
        results = None
        if last_date:
            AFTER='after:' + last_date
            # BEFORE='before:2023/8/25'
            QUERY = AFTER #  + ' ' + BEFORE
            results = service.users().messages().list(userId='me', labelIds=LABELID, pageToken=pageToken, maxResults=100, q=QUERY).execute() #, q=QUERY
        else:
            results = service.users().messages().list(userId='me', labelIds=LABELID, pageToken=pageToken, maxResults=100).execute()
        messages = results.get('messages', [])
        # retrieve gmail messages
        all_messages = get_individual_messages(service, messages)

        print_entries( all_messages )
        insert_multiple_entries( all_messages )

        pageToken = results.get('nextPageToken', [])
        while pageToken:
            results = service.users().messages().list(userId='me', labelIds=LABELID, pageToken = pageToken, maxResults=500).execute() #, q=QUERY
            messages = results.get('messages', [])
            all_messages = get_individual_messages(service, messages)
            print_entries( all_messages )
            insert_multiple_entries( all_messages )

            pageToken = results.get('nextPageToken', [])


        

    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f'An error occurred: {error}')


if __name__ == '__main__':
    main()
