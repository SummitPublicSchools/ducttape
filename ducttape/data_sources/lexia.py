from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import super
from future import standard_library
standard_library.install_aliases()
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import pandas as pd
from tempfile import mkdtemp
import shutil
import requests
import json
import imaplib
import email
import sys
import datetime as dt
import re
import io
import time

# local import
from ducttape.webui_datasource import WebUIDataSource
from ducttape.utils import (
    interpret_report_url,
    wait_for_any_file_in_folder,
    get_most_recent_file_in_dir,
    DriverBuilder,
    LoggingMixin,
)
from ducttape.exceptions import (
    InvalidLoginCredentials,
    ReportNotFound,
    InvalidIMAPParameters,
    NoDataError,
)

LEXIA_CSV_ENCODING = 'utf-8'


class Lexia(WebUIDataSource, LoggingMixin):
    """ Class for interacting with the web ui of Lexia
    """

    def __init__(self, username, password, wait_time, hostname, temp_folder_path=None, headless=False,
                 lexia_school_year_start_date=None,
                 district_export_email_address=None, district_export_email_password=None,
                 district_export_email_imap_uri=None, district_export_email_folder='Lexia District Exports',
                 district_export_email_wait_time=600, district_export_email_retry_frequency=30, district_id=None):
        super().__init__(username, password, wait_time, hostname, temp_folder_path, headless)
        self.lexia_school_year_start_date = lexia_school_year_start_date
        self.district_export_email_address = district_export_email_address
        self.district_export_email_password = district_export_email_password
        self.district_export_email_imap_uri = district_export_email_imap_uri
        self.district_export_email_folder = district_export_email_folder
        self.district_export_email_wait_time = district_export_email_wait_time
        self.district_export_email_retry_frequency = district_export_email_retry_frequency
        self.district_id = district_id
        self.uri_scheme = 'https://'
        self.base_url = self.uri_scheme + 'www.' + self.hostname

    def _login(self):
        """ Logs into the provided Lexia instance.
        """
        login_url = self.uri_scheme + 'auth.mylexia.com/mylexiaLogin'
        self.log.info('Logging into Lexia at: {}'.format(login_url))
        self.driver.get(login_url)
        elem = WebDriverWait(self.driver, self.wait_time).until(
            EC.presence_of_element_located((By.ID, 'username')))

        elem.clear()
        elem.send_keys(self.username)
        elem.send_keys(Keys.RETURN)
        time.sleep(2)
        elem = WebDriverWait(self.driver, self.wait_time).until(EC.presence_of_element_located((By.ID, 'login-password')))
        elem.send_keys(self.password)
        elem.send_keys(Keys.RETURN)

        # ensure that login is successful
        self.driver.get(self.base_url)

        if 'Welcome' in self.driver.title:
            self.driver.close()
            raise InvalidLoginCredentials

    def download_url_report(self, report_url, write_to_disk=None, **kwargs):
        """ Downloads a Lexia report at a URL for a page with an 'export' button.

        Args:
            report_url (string): Information pertaining to the path and query
                string for the report whose access is desired. Any filtering
                that can be done with a stateful URL should be included.
            write_to_disk (string): The path for a directory to store the
                downloaded file. If nothing is provided, the file will be
                stored in a temporary directory and deleted at the end of
                this function.
            **kwargs: additional arguments to pass to Pandas read_excel or
                read_csv (depending on the report_url)

        Returns: A Pandas DataFrame of the report contents.
        """

        report_download_url = interpret_report_url(self.base_url, report_url)

        # if user is trying to download a manage tab report (for convenience)
        if '/mylexiaweb/app/index.html#/groups/' in report_download_url:
            return self.download_manage_tab_report(report_url, write_to_disk, **kwargs)

        if write_to_disk:
            csv_download_folder_path = write_to_disk
        else:
            csv_download_folder_path = mkdtemp()
        self.driver = DriverBuilder().get_driver(csv_download_folder_path, self.headless)
        self._login()

        self.log.info('Getting report page at: {}'.format(report_download_url))
        self.driver.get(report_download_url)

        # find and click the download button
        elem = WebDriverWait(self.driver, self.wait_time).until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Export')]"))
        )

        self.log.info('Starting download of: '.format(report_download_url))
        elem.click()

        wait_for_any_file_in_folder(csv_download_folder_path, "xlsx")
        self.log.info('Download Finished.')

        df_report = pd.read_excel(get_most_recent_file_in_dir(csv_download_folder_path),
                                **kwargs)

        # if the dataframe is empty (the report had no data), raise an error
        if df_report.shape[0] == 0:
            raise ValueError('No data in report for user {} at url: {}'.format(
                self.username, interpret_report_url(self.base_url, report_url)))

        self.driver.close()

        if not write_to_disk:
            shutil.rmtree(csv_download_folder_path)

        return df_report

    def download_manage_tab_report(self, report_url, write_to_disk=None, **kwargs):
        """ Downloads a Lexia report from the 'Manage' tab.

        Args:
            report_url (string): Information pertaining to the path and query
                string for the report whose access is desired. Any filtering
                that can be done with a stateful URL should be included.
            write_to_disk (string): The path for a directory to store the
                downloaded file. If nothing is provided, the file will be
                stored in a temporary directory and deleted at the end of
                this function.
            **kwargs: additional arguments to pass to Pandas read_csv

        Returns: A Pandas DataFrame of the report contents.
        """
        if write_to_disk:
            csv_download_folder_path = write_to_disk
        else:
            csv_download_folder_path = mkdtemp()
        self.driver = DriverBuilder().get_driver(csv_download_folder_path, self.headless)
        self._login()

        report_download_url = interpret_report_url(self.base_url, report_url)
        self.log.info('Getting report page at: {}'.format(report_download_url))
        self.driver.get(report_download_url)

        # select all users and find the download button
        def check_for_export_button_enabled(driver, elem_select_all_locator, elem_export_locator):
            elem_select_all = driver.find_element(*elem_select_all_locator)
            if not elem_select_all.is_enabled():
                return False
            elem_select_all.click()
            if not elem_select_all.is_selected():
                return False
            elem_export = driver.find_element(*elem_export_locator)
            if elem_export.is_enabled() and elem_export.is_displayed():
                return elem_export
            else:
                return False

        # have to use a lambda because until expects a callable
        elem_export = WebDriverWait(self.driver, self.wait_time).until(
            lambda x: check_for_export_button_enabled(self.driver, (By.NAME, "lexia-select-all"),
                                                      (By.XPATH, "//button[contains(text(), 'Export')]"))
        )
        self.log.info('Starting download of: '.format(report_download_url))
        elem_export.click()

        wait_for_any_file_in_folder(csv_download_folder_path, "xls")
        self.log.info('Download Finished.')

        df_report = pd.read_csv(get_most_recent_file_in_dir(csv_download_folder_path),
                                sep='\t', **kwargs)

        # if the dataframe is empty (the report had no data), raise an error
        if df_report.shape[0] == 0:
            raise ValueError('No data in report for user {} at url: {}'.format(
                self.username, interpret_report_url(self.base_url, report_url)))

        self.driver.close()

        if not write_to_disk:
            shutil.rmtree(csv_download_folder_path)

        return df_report

    def download_district_export_core5_monthly(self, write_to_disk=None, pandas_read_csv_kwargs={},
                                               period_end_date=dt.datetime.now().date()):
        return self._download_district_export(
            report_type='export',
            period_end_date=period_end_date,
            write_to_disk=write_to_disk,
            pandas_read_csv_kwargs=pandas_read_csv_kwargs
        )

    def download_district_export_core5_year_to_date(self, write_to_disk=None, pandas_read_csv_kwargs={},
                                                    period_end_date=dt.datetime.now().date()):
        return self._download_district_export(
            report_type='expytd',
            period_end_date=period_end_date,
            write_to_disk=write_to_disk,
            pandas_read_csv_kwargs=pandas_read_csv_kwargs
        )

    def download_district_export_powerup_year_to_date(self, write_to_disk=None, pandas_read_csv_kwargs={},
                                                      period_end_date=dt.datetime.now().date()):
        return self._download_district_export(
            report_type='pupytd',
            period_end_date=period_end_date,
            write_to_disk=write_to_disk,
            pandas_read_csv_kwargs=pandas_read_csv_kwargs
        )

    def _download_district_export(self, report_type, period_end_date, period_start_date=None,
                                  write_to_disk=None, pandas_read_csv_kwargs={}):
        if not period_start_date:
            period_start_date = self.lexia_school_year_start_date
        self.__request_district_export(report_type, period_start_date, period_end_date)

        df_report = None
        number_retries = int(self.district_export_email_wait_time / self.district_export_email_retry_frequency)
        for retry_count in range(0, number_retries):
            if retry_count > 0:
                time.sleep(self.district_export_email_retry_frequency)
            self.log.info(str(self.district_id) + ': get export_id from email, try: ' + str(retry_count))
            try:
                export_id = self.__get_exportid_from_email()
            except ValueError as err:
                self.log.debug(err)
                self.log.warning('{}: No export_id found in email, retrying in {} seconds.'.format(
                    self.district_id,
                    self.district_export_email_retry_frequency
                ))
                time.sleep(self.district_export_email_retry_frequency)
                continue

            try:
                df_report = self.__download_export_for_exportid(export_id, write_to_disk, pandas_read_csv_kwargs)
                break
            except NoDataError as e:
                self.log.warning('{}: {} Retrying in {} seconds.'.format(
                    self.district_id,
                    e,
                    self.district_export_email_retry_frequency
                ))
        if df_report is None:
            raise ReportNotFound('No email was received with report id. Make sure the emails are not going to spam.')
        else:
            return df_report

    def __request_district_export(self, report_type, period_start_date=None, period_end_date=None,
                                  write_to_disk=None):
        """
        Logs into Lexia and submits the request to generate a district export
        :param report_type: The text from one of 'Report type' options listed in the myLexia
            'District Exports' modal.
        :param period_start_date: The start date for the report request (unsure if this actually
            affects the data returned if it is different from the school year start date set
            for your Lexia instance)
        :param period_end_date: The end date for the report request (unsure if this actually
            affects the data returned if it is different from the day on which the request is made)
        :param write_to_disk: The path to save the CSV to.
        :return: Boolean. Whether or not the export request was successful.
        """
        if write_to_disk:
            csv_download_folder_path = write_to_disk
        else:
            csv_download_folder_path = self.temp_folder_path
        self.driver = DriverBuilder().get_driver(csv_download_folder_path, self.headless)
        self._login()

        # use requests to post the download request
        with requests.Session() as s:
            for cookie in self.driver.get_cookies():
                s.cookies.set(cookie['name'], cookie['value'])

            payload = {
                "districtID": self.district_id,
                "type": report_type,
                "email": self.district_export_email_address,
                "startDate": period_start_date.strftime("%Y-%m-%d"),
                "endDate": period_end_date.strftime("%Y-%m-%d")
            }
            self.log.info('{}: Export request payload: {}'.format(self.district_id, payload))
            download_response = s.put(self.base_url + '/exportData/progress', data=payload)

            if download_response.ok:
                self.log.info('{}: Export request for {} succeeded for user: {}'.format(
                    self.district_id, report_type, self.username
                ))
                j_data = json.loads(download_response.content.decode())
                self.log.info(j_data)
                return True
            else:
                self.log.info('{}: Export request for {} FAILED  for user: {}'.format(
                    self.district_id, report_type, self.username
                ))
                self.log.info(download_response.content)
                return False

    def __get_exportid_from_email(self):
        """Log into an IMAP email server and get messages in a specific folder.
        Checks for a new Lexia export_id in those messages.

        Returns:
            int: the export_id
        """
        self.log.info('Checking email for latest report ID for district_id: ' + str(self.district_id))
        imap_conn = imaplib.IMAP4_SSL(self.district_export_email_imap_uri)

        try:
            imap_conn.login(self.district_export_email_address, self.district_export_email_password)
        except imaplib.IMAP4.error:
            self.log.error('Email login failed for: ' + self.district_export_email_address)
            sys.exit(1)

        rv, data = imap_conn.select('"{}"'.format(self.district_export_email_folder))
        if rv == 'OK':
            self.log.info('Processing mailbox for ' + self.district_export_email_address +
                          ' in folder "' + self.district_export_email_folder + '"')
            export_id = self.__extract_lexia_export_id_from_email(imap_conn)
            if export_id == -1:
                raise ValueError('No new export_id found on ' + self.district_export_email_address)
            else:
                imap_conn.close()
                return export_id

        else:
            raise InvalidIMAPParameters(
                "ERROR: Unable to open mailbox. Check your parameters and email folder. Message: ", rv)
            imap_conn.logout()

    def __extract_lexia_export_id_from_email(self, imap_conn):
        """ Extract the export_id that is sent by Lexia that is needed to
        download the prepared report export.

        Email messages in Gmail aren't sorted can can't be sorted using
        regular IMAP functions (Gmail does not support them). Therefore
        we will search within the folder for messages in the last day.

        Args:
            imap_conn (imaplib.IMAP4_SSL): A current connection to an IMAP
                email account.

        Returns:
            int: The new export_id
        """
        # get all messages received in the last day
        rv, data = imap_conn.search(None, '(SINCE ' +
                                    (dt.datetime.now() - dt.timedelta(1)).strftime("%d-%b-%Y") + ')')
        if rv != 'OK':
            self.log.warning("No email messages found!")
            # TODO change this to raise an error
            return -1

        highest_export_id = -1
        for num in data[0].split():
            rv, data = imap_conn.fetch(num, '(RFC822)')
            if rv != 'OK':
                # TODO change this to raise an error
                self.log.error("ERROR getting email message", num)
                return -1

            msg = email.message_from_bytes(data[0][1])
            self.log.info('Processing Message %s, Raw Date: %s' % (num, msg['Date']))
            highest_export_id = 0
            for part in msg.walk():
                # each part is a either non-multipart, or another multipart message
                # that contains further parts... Message is organized like a tree
                if part.get_content_type() == 'text/plain':
                    # get the raw text
                    part_str = part.get_payload()
                    # extract the report id
                    match = re.search(r'(?<=id=)(\d*?)(?=\s)', part_str)
                    if match:
                        export_id = int(match.group(0))
                        self.log.info('export_id found: ' + str(export_id))
                        if export_id > highest_export_id:
                            highest_export_id = export_id
                    else:
                        return -1

        return highest_export_id

    def __download_export_for_exportid(self, export_id, write_to_disk=None, pandas_read_csv_kwargs={}):
        """Logs into lexia and downloads the report associated with a specific
        export_id.

        Args:
            export_id (int): The Lexia export id to download.
            write_to_disk (str): A path where the CSV that has been downloaded should be written to disk.
            pandas_read_csv_kwargs (dict): kwargs to pass to the Pandas read_csv function as necessary
        Returns:
            A Pandas dataframe with the report contents
        """
        self.log.info(str(self.district_id) + ': downloading report with export_id=' +
                      str(export_id))
        with requests.Session() as s:
            for cookie in self.driver.get_cookies():
                s.cookies.set(cookie['name'], cookie['value'])

            export_url = self.base_url + '/reports/get_export.php' + '?id=' + str(export_id)
            download_response = s.get(export_url)

            self.log.info('Report download request response for export_id {}: {}'.format(
                export_id,
                download_response.content
            ))

            if download_response.ok:
                df_report = pd.read_csv(io.StringIO(download_response.content.decode(LEXIA_CSV_ENCODING)),
                                        **pandas_read_csv_kwargs)

                # if the dataframe is empty (the report had no data), raise an error
                if df_report.shape[0] == 0:
                    raise NoDataError('No data in report for user {} at url: {}'.format(
                        self.username, export_url))
            else:
                raise ValueError('Report download request failed')

        self.driver.close()

        if write_to_disk:
            df_report.to_csv(write_to_disk)

        return df_report
