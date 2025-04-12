# from __future__ import print_function
# import os
# from googleapiclient.discovery import build
# from google_auth_oauthlib.flow import InstalledAppFlow
# from google.auth.transport.requests import Request
# from google.oauth2.credentials import Credentials

# # Scopes required for accessing Google Sheets and Drive
# SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

# # Tab color used for all sheets
# TAB_COLORS = [{"red": 1, "green": 0, "blue": 0}]

# # Authenticate and return Google Sheets API service
# def fetch_service():
#     creds = None
#     if os.path.exists('token.json'):
#         creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
#     if not creds or not creds.valid:
#         if creds and creds.expired and creds.refresh_token:
#             creds.refresh(Request())
#         else:
#             flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
#             creds = flow.run_local_server(port=0)
#         with open('token.json', 'w') as token:
#             token.write(creds.to_json())
    
#     service = build('sheets', 'v4', credentials=creds)
#     return service

# # Create a Google Spreadsheet with given title and multiple named sheets
# def create_spreadsheet(service, title, sheets_names):
#     sheets = []
#     for index, name in enumerate(sheets_names):
#         sheet_info = {
#             'properties': {
#                 "sheetId": index,
#                 "title": name,
#                 "index": index,
#                 "tabColor": TAB_COLORS[0]
#             }
#         }
#         sheets.append(sheet_info)
#     spreadsheet_body = {
#         'properties': {
#             'title': title
#         },
#         'sheets': sheets
#     }
#     spreadsheet = service.spreadsheets().create(body=spreadsheet_body, fields='spreadsheetId').execute()
#     return spreadsheet.get('spreadsheetId')

# # Generate 2D list (with headers) from dictionary of news data
# def generate_values(raw_data):
#     news_rows = [list(item.values()) for _, item in raw_data.items()]
#     try:
#         columns = list(raw_data[1].keys())
#     except KeyError:
#         columns = ["source", "author", "title", "description", "url", "publishedAt"]
#     return [columns] + news_rows

# # Write values to the given spreadsheet and range
# def write_single(service, spreadsheet_id, target_range, values):
#     body = {
#         'values': generate_values(values)
#     }
#     result = service.spreadsheets().values().update(
#         spreadsheetId=spreadsheet_id,
#         range=target_range,
#         valueInputOption='RAW',
#         body=body
#     ).execute()
#     print(f"{result.get('updatedCells')} cells updated.\nRange: {target_range}")

# # Rename a specific sheet within the spreadsheet
# def update_sheet(service, spreadsheet_id, sheet_id, new_title):
#     requests = [{
#         'updateSheetProperties': {
#             'properties': {
#                 'sheetId': sheet_id,
#                 'title': new_title
#             },
#             'fields': 'title'
#         }
#     }]
#     body = {
#         'requests': requests
#     }
#     response = service.spreadsheets().batchUpdate(
#         spreadsheetId=spreadsheet_id,
#         body=body
#     ).execute()
#     print(f'Sheet updated {response}')

from __future__ import print_function
import os.path
import os
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

Colors = [{"red": 1, "green": 0, "blue": 0}]

def fetch_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    service = build('sheets', 'v4', credentials=creds)
    return service

def create_spreadsheet(service, title, sheets_names):
    sheets = []
    counter = 0
    for sheet in sheets_names:
        sheet_info = {
                'properties': {
                    "sheetId": counter,
                    "title": sheet,
                    "index": counter,
                    "tabColor": Colors[0]
                }
            }
        counter += 1
        sheets.append(sheet_info)
    spreadsheet = {
        'properties': {
            'title': title
        },
        'sheets': sheets
    }
    spreadsheet = service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
    return spreadsheet.get('spreadsheetId')

def write_single(service, spreadsheet_id, range, values):
    values = generate_values(values)
    body = {
        'values': values
    }
    result = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range,
        valueInputOption='RAW',
        body=body
    ).execute()
    print(f"{result.get('updatedCells')} cells updated.\n range: {range}")

def generate_values(raw_data):
    news = [list(value.values()) for _, value in raw_data.items()]
    try:
        columns = list(raw_data[1].keys())
    except KeyError:
        columns = ["source", "author", "title", "description", "url", "publishedAt"]
    return [columns] + news

def update_sheet(services, spreadsheet_id, sheet_id, news_title):
    requests = list()
    requests.append({
        'updateSheetProperties': {
            'properties': {
                'sheetId': sheet_id,
                'title': news_title
            },
            'fields': 'title'
        }
    })
    body = {
        'requests': requests
    }
    response = services.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=body
    ).execute()
    print(f'Sheet updated {response}')