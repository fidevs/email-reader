from __future__ import print_function
from typing import List

import os.path
import base64
import time
import pandas as pd
import psycopg2

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

QUERY = 'from:fidev.id@outlook.com is:unread has:attachment subject:Reporte mensual'
API_NAME = 'gmail'
API_VERSION = 'v1'
TOKEN_STORE = 'token.json'
CREDS_FILE = 'credentials.json'
# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.modify']


# Exceptions
class GmailException(Exception):
    """Gmail base exception class"""


class NoEmailFound(GmailException):
    """No email found exception"""


def get_database_connection():
    try:
        connection = psycopg2.connect(
            host='localhost',
            user='arkon',
            password='4rk0n',
            database='bimbo_xls'
        )
        print("conexión exitosa")
        return connection
    except Exception as ex:
        print(ex)


def gmail_authenticate():
    """Authenticate with Gmail API"""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(TOKEN_STORE):
        creds = Credentials.from_authorized_user_file(TOKEN_STORE, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(TOKEN_STORE, 'w') as token:
            token.write(creds.to_json())

    global service
    try:
        # Build the Gmail API service
        service = build(API_NAME, API_VERSION, credentials=creds)
    except HttpError as error:
        service = None
        print(f'An error occurred building API service: {error}')


def search_emails():
    """Search for new emails"""
    print('Searching for new messages...')
    try:
        # Call the Gmail API
        response = service.users().messages().list(userId='me', q=QUERY).execute()
        if response['resultSizeEstimate'] <= 0:
            print('No new messages found.')
            return []
        print(f"Found {response['resultSizeEstimate']} new message(s)")
        # TODO: handle more emails
        return response.get('messages')
    except Exception as e:
        print(F'Error searching new emails: {e}')


def get_attachment_data(mail_id, attachment_id):
    """Obtain email attachment data"""
    print(f'     Getting data of attachment: {attachment_id}...')
    response = None
    try:
        # Search attachment by message id
        response = service.users().messages().attachments().get(
            userId='me',
            messageId=mail_id,
            id=attachment_id
        ).execute()
        print('     Attachment loaded!')
    except Exception as e:
        print(f'Error getting attachment data: {e}')

    if response:
        # Decode file data
        print('     Decoding attachment...')
        return base64.urlsafe_b64decode(response.get('data').encode('UTF-8'))
    return None


def get_message_detail(message_id, format='metadata', metadata_headers: List = None):
    """Obtain message detail"""
    print(f'     Getting message detail...')
    response = None
    try:
        response = service.users().messages().get(
            userId='me',
            id=message_id,
            format=format,
            metadataHeaders=metadata_headers
        ).execute()
        print(f'     Message detail loaded!')
    except Exception as e:
        print(f'Error getting message detail: {e}')
    return response


def mark_message_as_read(message_id):
    print('     Marking message as read...')
    try:
        service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        print('     Message marked as read!')
    except Exception as e:
        print(f'Error marking message as READ: {e}')


def main():
    print('Logging in...')
    gmail_authenticate()

    if service is None:
        print('Not API service available, ending execution...')
        return
    print('Success login!')

    condition = 1
    while condition == 1:
        emails = search_emails()
        for email in emails:
            print(f"> Working with message: {email['id']}")
            msg_detail = get_message_detail(email['id'], format='full', metadata_headers=['parts'])
            if msg_detail:
                msg_detail_payload = msg_detail.get('payload')

                if 'parts' in msg_detail_payload:
                    for msg_payload in msg_detail_payload['parts']:
                        body = msg_payload['body']
                        if 'attachmentId' in body:
                            attachment_id = body['attachmentId']
                            attachment_content = get_attachment_data(email['id'], attachment_id)
                            if attachment_content:
                                query = generate_updates_from_file(attachment_content)
                                try:
                                    connection = get_database_connection()
                                    cursor = connection.cursor()
                                    print(query)
                                    cursor.execute(query)
                                    cursor.close()
                                    connection.commit()
                                    connection.close()
                                    print('Query success')
                                    mark_message_as_read(email['id'])
                                except Exception as ex:
                                    print(f'SQL error: {ex}')

        print('Waiting 10 seconds for next execution...\n\n\n')
        time.sleep(10)


def generate_updates_from_file(file):
    df = pd.read_excel(file, index_col=0)
    query = ''
    index_list = list(df.index.values)
    for label, content in df.items():
        for idx in index_list:
            new_query = "UPDATE period_org_module SET status = '{}' WHERE org_name = '{}' AND module = '{}';"\
                .format(content[idx], label, idx.replace("'", "''"))
            query = query + new_query + '\n'
    return query


if __name__ == '__main__':
    main()
