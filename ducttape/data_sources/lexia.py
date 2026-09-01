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
import os
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
        time.sleep(5)

        # ensure that login is successful
        try:
            elem = WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located((By.ID, 'mat-tab-link-0'))
            )
            self.log.info('Login sucessful!')
        except:
            self.driver.quit()
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

        self.driver.quit()

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

        self.driver.quit()

        if not write_to_disk:
            shutil.rmtree(csv_download_folder_path)

        return df_report

    def download_district_export_core5_monthly(self, write_to_disk=None, pandas_read_csv_kwargs={}):
        return self._download_district_export(
            report_type='export',
            write_to_disk=write_to_disk,
            pandas_read_csv_kwargs=pandas_read_csv_kwargs
        )

    def download_district_export_core5_year_to_date(self, write_to_disk=None, pandas_read_csv_kwargs={}):
        return self._download_district_export(
            report_type='expytd',
            write_to_disk=write_to_disk,
            pandas_read_csv_kwargs=pandas_read_csv_kwargs
        )

    def download_district_export_powerup_year_to_date(self, write_to_disk=None, pandas_read_csv_kwargs={}):
        return self._download_district_export(
            report_type='pupytd',
            write_to_disk=write_to_disk,
            pandas_read_csv_kwargs=pandas_read_csv_kwargs
        )
    
    def download_district_export_powerup_detailed_student(self, write_to_disk=None, pandas_read_csv_kwargs={}):
        return self._download_district_export(
            report_type='powerup_detailed',
            write_to_disk=write_to_disk,
            pandas_read_csv_kwargs=pandas_read_csv_kwargs
        )

    def _download_district_export(self, report_type, write_to_disk=None, pandas_read_csv_kwargs={}):
        was_request_successful = self.__request_district_export(report_type, write_to_disk=write_to_disk)
        assert was_request_successful, 'Export request failed.'

        df_report = None
        number_retries = int(self.district_export_email_wait_time / self.district_export_email_retry_frequency)
        for retry_count in range(0, number_retries):
            if retry_count > 0:
                time.sleep(self.district_export_email_retry_frequency)
            self.log.info(str(self.district_id) + ': get export_id from email, try: ' + str(retry_count))
            try:
                export_id = self.__get_exportid_from_email()
                if export_id == 0:
                    raise ValueError('export_id = 0, indicating no valid exports were found.')
            except ValueError as err:
                self.log.debug(err)
                self.log.warning('{}: No export_id found in email, retrying in {} seconds.'.format(
                    self.district_id,
                    self.district_export_email_retry_frequency
                ))
                time.sleep(self.district_export_email_retry_frequency)
                continue

            try:
                # Note: If the most recent exportid in the email folder is from a previously requested export,
                #    then this download will fail on the Lexia side, and the function will try again after a wait.
                df_report = self.__download_export_for_exportid(export_id, write_to_disk, pandas_read_csv_kwargs)
                break
            except NoDataError as e:
                self.log.warning('{}: {} Retrying in {} seconds.'.format(
                    self.district_id,
                    e,
                    self.district_export_email_retry_frequency
                ))
            except:
                self.log.warning(f'An exception occurred, likely that the report is not ready yet. Retrying in {self.district_export_email_retry_frequency} seconds.')

        # Regardless of outcome, end the driver instance
        self.driver.quit()

        # Remove the temp folder if used
        if not write_to_disk:
            shutil.rmtree(self._export_download_folder, ignore_errors=True)
        
        if df_report is None:
            raise ReportNotFound('No email was received with report id. Make sure the emails are not going to spam.')
        else:
            return df_report

    def __request_district_export(self, report_type, write_to_disk=None):
        """
        [Developed with Claude]

        Logs into Lexia and submits the request to generate a district export
        by navigating to the actual 'District Exports' modal via Selenium.

        :param report_type: The "value" from one of 'Report type' options listed in the myLexia
            'District Exports' modal.
        :return: Boolean. Whether or not the export request was successful.
        """
        if write_to_disk:
            csv_download_folder_path = write_to_disk
        else:
            csv_download_folder_path = mkdtemp()

        # Store this so __download_export_for_exportid uses the SAME folder
        # the browser was actually configured to download into.
        self._export_download_folder = csv_download_folder_path

        self.driver = DriverBuilder().get_driver(csv_download_folder_path, self.headless)
        self._login()

        # Click the "District Exports" button to open the modal
        self.log.info(2)
        export_button = WebDriverWait(self.driver, self.wait_time).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'District Exports')]"))
        )
        export_button.click()

        # Wait for the dialog to render
        self.log.info(3)
        WebDriverWait(self.driver, self.wait_time).until(
            EC.visibility_of_element_located((By.ID, "email"))
        )

        # Fill in the email field
        self.log.info(4)
        email_field = self.driver.find_element(By.ID, "email")
        email_field.clear()
        email_field.send_keys(self.district_export_email_address)

        # Select the correct radio button for the report type
        # (report_type values match the radio input 'value' attributes exactly,
        #  e.g. 'export', 'expytd', 'core5_detailed', 'pupytd',
        #  'powerup_monthly', 'powerup_detailed')
        self.log.info(5)
        radio_input = WebDriverWait(self.driver, self.wait_time).until(
            EC.presence_of_element_located(
                (By.XPATH, "//input[@type='radio' and @value='{}']".format(report_type))
            )
        )
        # Click the associated label, since the radio input itself is visually hidden/overlaid
        self.log.info(6)
        label = self.driver.find_element(By.XPATH, "//label[@for='{}']".format(radio_input.get_attribute("id")))
        label.click()

        # Click Submit
        self.log.info(7)
        submit_button = WebDriverWait(self.driver, self.wait_time).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Submit')]"))
        )
        submit_button.click()

        # Wait briefly for the confirmation notification to appear, confirming success
        try:
            self.log.info(8)
            WebDriverWait(self.driver, self.wait_time).until(
                EC.visibility_of_element_located((By.XPATH, "//div[contains(@class, 'notification') and contains(@class, 'success')]"))
            )
            self.log.info('{}: Export request for {} succeeded for user: {}'.format(
                self.district_id, report_type, self.username
            ))
            return True
        except Exception as e:
            self.log.info('{}: Export request for {} FAILED for user: {}'.format(
                self.district_id, report_type, self.username
            ))
            self.log.info(str(e))
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

        Email messages in Gmail can't be sorted using regular IMAP functions 
        (Gmail does not support them) and search can only be done by dates, 
        not times. Therefore, we will search within the folder for messages 
        since yesterday.

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

        return highest_export_id

    def __download_export_for_exportid(self, export_id, write_to_disk=None, pandas_read_csv_kwargs={}):
        """
        [Developed with Claude]

        Downloads the report associated with a specific export_id by having
        the browser itself navigate to the export URL, letting the existing
        authenticated session handle it (avoids cross-domain cookie issues).

        Args:
            export_id (int): The Lexia export id to download.
            write_to_disk (str): An option path where the CSV that has been downloaded should be written 
                to disk.
            pandas_read_csv_kwargs (dict): kwargs to pass to the Pandas read_csv function as necessary
        Returns:
            A Pandas dataframe with the report contents
        """
        self.log.info(str(self.district_id) + ': downloading report with export_id=' +
                    str(export_id))

        download_folder = write_to_disk if write_to_disk else self._export_download_folder
        export_url = self.base_url + '/reports/get_export.php' + '?id=' + str(export_id)

        self.log.info('Navigating browser to export URL: {}'.format(export_url))
        self.driver.get(export_url)

        # Give the browser a moment to either download the file or render a
        # response (e.g. an error/login page) so we can distinguish the two.
        file_found = wait_for_any_file_in_folder(download_folder, "csv", timeout=30)
        if not file_found:
            # No file appeared -- check what the browser actually loaded
            page_source_snippet = self.driver.page_source[:500]
            self.log.error('No CSV file appeared after navigating to export URL. '
                            'Page source starts with: {}'.format(page_source_snippet))
            raise NoDataError(
                'No CSV downloaded for export_id {}; browser may not be authenticated '
                'or export not ready.'.format(export_id)
            )

        downloaded_path = get_most_recent_file_in_dir(download_folder)
        self.log.info('Download finished: {}'.format(downloaded_path))

        df_report = pd.read_csv(downloaded_path, **pandas_read_csv_kwargs)

        if df_report.shape[0] == 0:
            raise NoDataError('No data in report for user {} at url: {}'.format(
                self.username, export_url))

        return df_report