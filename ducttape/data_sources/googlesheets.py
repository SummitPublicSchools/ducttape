"""
ducttape.data_sources.googlesheets
~~~~~~~~~~~~~~
This module contains Client class responsible for communicating with
Google Data API.
"""
try:
    import xml.etree.cElementTree as ElementTree
except:
    from xml.etree import ElementTree

import json
import re
import logging
from ducttape.httpsession import HTTPSession
import pandas as pd
import numpy as np
from ducttape.exceptions import RequestError
from ducttape.exceptions import IncorrectCellLabel
from ducttape.exceptions import WorksheetNotFound
from ducttape.exceptions import InvalidDimension
from oauth2client.service_account import ServiceAccountCredentials

# create module-level logger
LOGGER = logging.getLogger('sps-automation.data_sources.googlesheets')

MAGIC_NUMBER = 64
UPLOAD_BATCH_SIZE = 1000
CELL_ADDR_RE = re.compile(r'([A-Za-z]+)([1-9]\d*)')


class GoogleSpreadsheet(object):
    """An instance of this class communicates with Google Data API.
    
    :param auth: An OAuth2 credential object. Credential objects are those created by the
                 oauth2client library. https://github.com/google/oauth2client
    :param http_session: (optional) A session object capable of making HTTP requests while persisting headers.
                                    Defaults to :class:`~ducttape.httpsession.HTTPSession`.
    
    >>> c = ducttape.data_sources.GoogleSpreadSheet(auth=OAuthCredentialObject)
    
    """

    def __init__(self, auth, http_session=None):
        self.logger = logging.getLogger('sps-automation.data_sources.googlesheets.GoogleSpreadsheet')
        self.logger.debug('creating instance of GoogleSpreadsheet')
        self.auth = auth
        self.session = http_session or HTTPSession()
        self._login()

    def _ensure_xml_header(self, data):
        if data.startswith(b'<?xml'):
            return data
        else:
            return b'<?xml version="1.0" encoding="utf8"?>' + data

    def _login(self):
        """Authorize client."""
        self.logger.debug('logging into Google using OAUTH')
        if not self.auth.access_token or \
                (hasattr(self.auth, 'access_token_expired') and self.auth.access_token_expired):
            import httplib2

            http = httplib2.Http()
            self.auth.refresh(http)

        self.session.add_header('Authorization', "Bearer " + self.auth.access_token)

    def download_worksheet_range(self, spreadsheet_id, range_a1_notation, header_row=None):
        if header_row:
            header_index = header_row
        else:
            header_index = 0

        self.logger.info('downloading spreadsheet: {}; range: {}; header_index: {}'.format(spreadsheet_id,
                                                                                            range_a1_notation,
                                                                                            header_index))

        req_url = "https://sheets.googleapis.com/v4/spreadsheets/{}/values/{}".format(spreadsheet_id, range_a1_notation)

        self.logger.debug('sending GET request: {}'.format(req_url))

        response = self.session.get(req_url)

        self.logger.debug('response status: {}'.format(response.status_code))
        self.logger.debug('response content: {}'.format(response.content))

        if response.ok:
            value_range = json.loads(response.content.decode('utf-8'))

        if value_range['majorDimension'] == 'ROWS':
            header = value_range['values'][header_index]
            # pandas needs a two-dimensional array with rows, hence the extra square brackets below
            rows = value_range['values'][header_index + 1:]

        # the arrays that represent the rows in the json returned from the API are not the
        # full width of the row. The width of the row only goes up to the right most cell
        # with data in it. In order to create a Pandas DataFrame with this information,
        # we need to make the lists that represent the rows the same length as the number
        # of column headers that were returned by the Sheets API.
        for row in rows:
            while len(row) < len(header):
                row.append(np.nan)

            while len(row) > len(header):
                row.pop(-1)

        df_worksheet_range = pd.DataFrame(rows, columns=header)

        # turn whitespace-only strings into np.nan
        df_worksheet_range = df_worksheet_range.replace(r'^\s*$', np.nan, regex=True)

        return df_worksheet_range

    def clear_worksheet_range(self, spreadsheet_id, range_a1_notation):
        self.logger.info('clearing worksheet range for spreadsheet_id: {}; range: {}'.format(spreadsheet_id,
                                                                                              range_a1_notation))
        req_url = "https://sheets.googleapis.com/v4/spreadsheets/{}/values/{}:clear".format(spreadsheet_id,
                                                                                            range_a1_notation)

        self.logger.debug('sending POST request: {}'.format(req_url))

        response = self.session.post(req_url)

        self.logger.debug('response status: {}'.format(response.status_code))
        self.logger.debug('response content: {}'.format(response.content))

        if response.ok:
            return True
        else:
            return False

    def get_worksheet_dimensions(self, spreadsheet_id, worksheet_name):
        self.logger.info('getting worksheet dimensions for sheet: {} in spreadsheet_id: {}'.format(worksheet_name,
                                                                                                    spreadsheet_id))
        req_url = "https://sheets.googleapis.com/v4/spreadsheets/{}".format(spreadsheet_id)
        req_params = {'includeGridData': 'False'}

        self.logger.debug('sending GET request: {}; params: '.format(req_url, req_params))

        response = self.session.get(req_url, params=req_params)

        self.logger.debug('response status: {}'.format(response.status_code))
        self.logger.debug('response content: {}'.format(response.content))

        if not response.ok:
            raise RequestError

        spreadsheet = json.loads(response.content.decode('utf-8'))

        sheets = spreadsheet['sheets']

        for sheet in sheets:
            if sheet['properties']['title'] == worksheet_name:
                grid_properties = sheet['properties']['gridProperties']
                return grid_properties['rowCount'], grid_properties['columnCount']

        raise WorksheetNotFound

    def get_worksheet_id(self, spreadsheet_id, worksheet_name):
        self.logger.info('getting worksheet id for spreadsheet_id: {}; sheet_name: {}'.format(spreadsheet_id,
                                                                                              worksheet_name))
        req_url = "https://sheets.googleapis.com/v4/spreadsheets/{}".format(spreadsheet_id)

        self.logger.debug('sending GET request: {};'.format(req_url))

        response = self.session.get(req_url)

        self.logger.debug('response status: {}'.format(response.status_code))
        self.logger.debug('response content: {}'.format(response.content))

        if not response.ok:
            raise RequestError

        spreadsheet = json.loads(response.content.decode('utf-8'))

        sheets = spreadsheet['sheets']

        for sheet in sheets:
            if sheet['properties']['title'] == worksheet_name:
                return sheet['properties']['sheetId']

        raise WorksheetNotFound

    def _spreadsheet_batchupdate_request(self, spreadsheet_id, request_list, include_spreadsheet_in_response=False,
                                         response_include_grid_data=False):
        self.logger.info('sending _spreadsheet_batchupdate_request for spreadsheet_id: {}'.format(spreadsheet_id))

        req_url = "https://sheets.googleapis.com/v4/spreadsheets/{}:batchUpdate".format(spreadsheet_id)

        request_body = {
            "requests": request_list,
            "includeSpreadsheetInResponse": include_spreadsheet_in_response,
            "responseIncludeGridData": response_include_grid_data
        }

        data = json.dumps(request_body)

        self.logger.debug('sending POST request: {}'.format(req_url))
        self.logger.debug('request_body: {}'.format(request_body))

        response = self.session.post(req_url, data=data)

        self.logger.debug('response status: {}'.format(response.status_code))
        self.logger.debug('response content: {}'.format(response.content))

        if response.ok:
            return json.loads(response.content.decode('utf-8'))
        else:
            raise RequestError

    def delete_worksheet_dimension(self, spreadsheet_id, worksheet_name, dimension, start_index, end_index):
        self.logger.info('deleting {} {} in sheet: {} for spreadsheet_id: {}'.format(end_index - start_index,
                                                                                     dimension,
                                                                                     worksheet_name,
                                                                                     spreadsheet_id))
        if dimension.upper() not in ['ROWS', 'COLUMNS']:
            raise InvalidDimension

        dimension_range = {
            "sheetId": self.get_worksheet_id(spreadsheet_id, worksheet_name),
            "dimension": dimension.upper(),
            "startIndex": start_index,
            "endIndex": end_index
        }

        range = {
            "range": dimension_range
        }

        request = {
            'deleteDimension': range
        }

        response = self._spreadsheet_batchupdate_request(spreadsheet_id, [request])

        return True

        # TODO: Add checking of results in-function

    def delete_rows_from_bottom_of_worksheet(self, spreadsheet_id, worksheet_name, num_rows):
        # no logging - convenience function

        num_rows_current = self.get_worksheet_dimensions(spreadsheet_id, worksheet_name)[0]

        first_row_to_delete = num_rows_current - num_rows
        last_row_to_delete = num_rows_current

        self.delete_worksheet_dimension(spreadsheet_id, worksheet_name, 'ROWS', first_row_to_delete, last_row_to_delete)

        return True

    def delete_columns_from_right_of_worksheet(self, spreadsheet_id, worksheet_name, num_columns):
        # no logging - convenience function

        num_cols_current = self.get_worksheet_dimensions(spreadsheet_id, worksheet_name)[1]

        first_col_to_delete = num_cols_current - num_columns
        last_col_to_delete = num_cols_current

        self.delete_worksheet_dimension(spreadsheet_id, worksheet_name, 'COLUMNS', first_col_to_delete, last_col_to_delete)

        return True

    def append_worksheet_dimension(self, spreadsheet_id, worksheet_name, dimension, length):
        self.logger.info('appending {} {} to sheet: for spreadsheet_id: {}'.format(length, dimension, worksheet_name,
                                                                                   spreadsheet_id))
        if dimension.upper() not in ['ROWS', 'COLUMNS']:
            raise InvalidDimension

        append_dimension_request = {
            "sheetId": self.get_worksheet_id(spreadsheet_id, worksheet_name),
            "dimension": dimension.upper(),
            "length": length
        }

        request = {
            'appendDimension': append_dimension_request
        }

        response = self._spreadsheet_batchupdate_request(spreadsheet_id, [request])

        return True

        # TODO: Add checking of results in-function

    def append_rows_to_bottom_of_worksheet(self, spreadsheet_id, worksheet_name, num_rows):
        # no logging - convenience function

        self.append_worksheet_dimension(spreadsheet_id, worksheet_name, 'rows', num_rows)

        return True

    def append_columns_to_right_of_worksheet(self, spreadsheet_id, worksheet_name, num_columns):
        # no logging - convenience function

        self. append_worksheet_dimension(spreadsheet_id, worksheet_name, 'columns', num_columns)

        return True

    def set_worksheet_dimensions(self, spreadsheet_id, worksheet_name, num_rows, num_columns):
        self.logger.info(
            'setting dimensions of sheet: {} in spreadsheet_id: {} to {} rows, {} columns'.format(
                worksheet_name, spreadsheet_id, num_rows, num_columns
            ))
        ws_rows_current, ws_cols_current = self.get_worksheet_dimensions(spreadsheet_id, worksheet_name)

        if ws_rows_current > num_rows:
            # delete some rows
            rows_excess = ws_rows_current - num_rows
            self.delete_rows_from_bottom_of_worksheet(spreadsheet_id, worksheet_name, rows_excess)

        elif ws_rows_current < num_rows:
            # add some rows
            rows_needed = num_rows - ws_rows_current
            self.append_rows_to_bottom_of_worksheet(spreadsheet_id, worksheet_name, rows_needed)

        if ws_cols_current  > num_columns:
            # delete some cols
            pass
            columns_excess = ws_cols_current - num_columns
            self.delete_columns_from_right_of_worksheet(spreadsheet_id, worksheet_name, columns_excess)

        elif ws_cols_current < num_columns:
            # add some cols
            columns_needed = num_columns - ws_cols_current
            self.append_columns_to_right_of_worksheet(spreadsheet_id, worksheet_name, columns_needed)

        return True

    def update_worksheet_range(self, spreadsheet_id, range_a1_notation, rows):
        self.logger.info('sending update_worksheet_range for range: {} in spreadsheet_id: {}'.format(range_a1_notation,
                                                                                                     spreadsheet_id))
        req_url = "https://sheets.googleapis.com/v4/spreadsheets/{}/values/{}".format(spreadsheet_id, range_a1_notation)

        params = {
            'valueInputOption': 'RAW'
        }

        value_range = {
            'range': range_a1_notation,
            'majorDimension': 'ROWS',
            'values': rows
        }

        data = json.dumps(value_range)

        self.logger.debug('sending PUT request: {}; params: {}'.format(req_url, params))

        response = self.session.put(req_url, params=params, data=data)

        self.logger.debug('response status: {}'.format(response.status_code))
        self.logger.debug('response content: {}'.format(response.content))

        if response.ok:
            return True
        else:
            return False

    def replace_worksheet_with_dataframe(self, spreadsheet_id, worksheet_name, df, upper_left_cell=None,
                                         include_header=True):
        self.logger.info(
            "replacing sheet: '{}' with dataframe in spreadsheet_id: {} - starting in cell: {}".format(
                worksheet_name, spreadsheet_id, upper_left_cell
            ))
        # set up the range into which the dataframe should be placed
        range_start_a1 = upper_left_cell or 'A1'

        df_rows, df_cols = df.shape

        range_start_row_index, range_start_col_index = self._a1_to_rowcol_index(range_start_a1)

        # only -1 on col b/c row includes header row
        range_end_row_index = range_start_row_index + df_rows
        range_end_col_index = range_start_col_index + df_cols - 1

        range_end_a1 = self._rowcol_index_to_a1(range_end_row_index, range_end_col_index)

        range_a1_notation = "'{}'!{}:{}".format(worksheet_name, range_start_a1, range_end_a1)

        # set sheet dimensions accommodate the range
        self.set_worksheet_dimensions(spreadsheet_id, worksheet_name, range_end_row_index + 1, range_end_col_index + 1)

        # clear the range so that no old rows are left over
        self.clear_worksheet_range(spreadsheet_id, range_a1_notation)

        # batch the data and upload
        upload_array = list()
        index = 0

        # add the column headers
        if include_header:
            upload_array.append(list(df))

        df_rows_generator = df.iterrows()

        # The '1' is added here to make sure that the else runs for the last batch
        while index < df_rows + 1:
            if len(upload_array) < UPLOAD_BATCH_SIZE and (df_rows - index) > 0:
                rowlist = next(df_rows_generator)[1].tolist()
                # remove nan values from floats for upload
                for ix, val in enumerate(rowlist):
                    if type(val) is not str:
                        if np.isnan(float(val)):
                            rowlist[ix] = None
                upload_array.append(rowlist)
                index += 1

            # once full or no more rows, write data
            else:
                if include_header:
                    batch_range_start_row_index = range_start_row_index + index - len(upload_array) + 1
                else:
                    batch_range_start_row_index = range_start_row_index + index - len(upload_array)
                batch_range_start_col_index = range_start_col_index
                batch_range_start_a1 = self._rowcol_index_to_a1(batch_range_start_row_index, batch_range_start_col_index)
                batch_range_end_row_index = batch_range_start_row_index + len(upload_array)
                batch_range_end_col_index = range_end_col_index
                batch_range_end_a1 = self._rowcol_index_to_a1(batch_range_end_row_index, batch_range_end_col_index)

                batch_range_a1 = "'{}'!{}:{}".format(worksheet_name, batch_range_start_a1, batch_range_end_a1)

                self.update_worksheet_range(spreadsheet_id, batch_range_a1, upload_array)

                # reset upload_upload array, add current row loop's iteration
                upload_array = []

                # stop the loop after the last batch is uploaded
                if index == df_rows:
                    break

        self.logger.info(
            "replacing sheet: '{}' with dataframe in spreadsheet_id: {} - starting in cell: {} - COMPLETE".format(
                worksheet_name, spreadsheet_id, upper_left_cell
            ))
        return True

    def _rowcol_index_to_a1(self, row, col):
        """Translates a row and column cell address to A1 notation.
        :param row: The row of the cell to be converted.
                    Rows start at index 1.
        :param col: The column of the cell to be converted.
                    Columns start at index 1.
        :returns: a string containing the cell's coordinates in A1 notation.
        Example:
        >>> rowcol_to_a1(0, 0)
        A1
        """
        # plus one to zero-index the logic below
        row = int(row) + 1
        col = int(col) + 1

        if row < 1 or col < 1:
            raise IncorrectCellLabel('(%s, %s)' % (row, col))

        div = col
        column_label = ''

        while div:
            (div, mod) = divmod(div, 26)
            if mod == 0:
                mod = 26
                div -= 1
            column_label = chr(mod + MAGIC_NUMBER) + column_label

        label = '%s%s' % (column_label, row)

        return label

    def _a1_to_rowcol_index(self, label):
        """Translates a cell's address in A1 notation to a tuple of integers.
        :param label: String with cell label in A1 notation, e.g. 'B1'.
                      Letter case is ignored.
        :returns: a tuple containing `row` and `column` numbers. Both indexed
                  from 1 (one).
        Example:
        >>> a1_to_rowcol('A1')
        (0, 0)
        """
        m = CELL_ADDR_RE.match(label)
        if m:
            column_label = m.group(1).upper()
            row = int(m.group(2))

            col = 0
            for i, c in enumerate(reversed(column_label)):
                col += (ord(c) - MAGIC_NUMBER) * (26 ** i)
        else:
            raise IncorrectCellLabel(label)

        # -1 to zero index
        return (row - 1, col - 1)


def authorize_from_file(oauth_json_keyfile_path):
    """Shortcut function for getting a Google Spreadsheet object by just passing a path to OAUTH credentials."""
    scope = [
        'https://www.googleapis.com/auth/spreadsheets'
    ]

    credentials = ServiceAccountCredentials.from_json_keyfile_name(oauth_json_keyfile_path, scope)

    return GoogleSpreadsheet(credentials)
