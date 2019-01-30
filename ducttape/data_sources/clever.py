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
import logging
import requests
import pandas as pd
import io
import time
import shutil
from random import randint
from tempfile import mkdtemp
import warnings

# local import
from ducttape.webui_datasource import WebUIDataSource
from ducttape.exceptions import (
    ReportNotFound,
    InvalidLoginCredentials
)
from ducttape.utils import (
    configure_selenium_chrome,
    DriverBuilder,
    interpret_report_url,
    wait_for_any_file_in_folder,
    get_most_recent_file_in_dir,
    LoggingMixin
)


class Clever(WebUIDataSource, LoggingMixin):
    """ Class for interacting with the Clever Web UI
    """

    def __init__(self, username, password, wait_time, hostname='schools.clever.com',
                 temp_folder_path=None, headless=False):
        super().__init__(username, password, wait_time, hostname, temp_folder_path)
        self.uri_scheme = 'https://'
        self.base_url = self.uri_scheme + self.hostname
        self.headless = headless
        self.log.debug('creating instance of Clever')

    def _login(self):
        """ Logs into the provided Clever instance.
        """
        self.log.info('Logging into Clever instance: hostname, username: {}, {}'.format(
            self.hostname, self.username
        ))
        self.driver.get(self.base_url)
        # wait until login form available
        elem = WebDriverWait(self.driver, self.wait_time).until(
            EC.presence_of_element_located((By.NAME, 'username')))

        elem.clear()
        elem.send_keys(self.username)
        elem = self.driver.find_element_by_name("password")
        elem.send_keys(self.password)
        elem.send_keys(Keys.RETURN)

        # ensure that login is successful
        self.driver.get(self.base_url)

        if 'Clever | Home' not in self.driver.title:
            self.driver.close()
            raise InvalidLoginCredentials

    def download_url_report(self, report_url, collection, write_to_disk=None, **kwargs):
        """Currently a short cut for download_data_shared_with_application"""
        return self.download_data_shared_with_application(report_url, collection, write_to_disk, **kwargs)

    def download_data_shared_with_application(self, application_page_url, collection,
                                              write_to_disk=None, **kwargs):
        """
        Downloads the students shared with a particular application through Clever.
        :param application_page_url: The url for the main Clever management page for a
            particular application. For example, for My Lexia, this would be
            https://schools.clever.com/applications/lexia-mylexia
        :param collection: A string of 'schools', 'students', 'sections', 'teachers', 'schooladmins'
            that indicates which shared data to download
        :param write_to_disk: A path to a directory where the downloaded CSV should be saved.
            If nothing is passed, it will not be saved and only a Pandas DataFrame will be returned.
        :param kwargs: Additional keyword arguments to be passed to the Pandas read_csv function.
        :return: A Pandas DataFrame of the indicated collection download.
        """
        collection = collection.lower().replace(' ', '')
        if collection not in ['schools', 'students', 'sections', 'teachers', 'schooladmins']:
            raise ReportNotFound(
                (
                    "Argument for collection '{collection}' is not a valid. Please choose from: "
                    "'schools', 'students', 'sections', 'teachers', 'schooladmins'."
                ).format(collection=collection)
            )
        report_access_page_url = interpret_report_url(self.base_url, application_page_url)

        if write_to_disk:
            csv_download_folder_path = write_to_disk
        else:
            csv_download_folder_path = mkdtemp()
        self.driver = DriverBuilder().get_driver(csv_download_folder_path, self.headless)
        self._login()

        self.log.debug('Getting report access page at: {}'.format(report_access_page_url))
        self.driver.get(report_access_page_url)

        # find and click the download button based on the collection desired
        elem = WebDriverWait(self.driver, self.wait_time).until(
            EC.presence_of_element_located(
                (By.XPATH, "//a[contains(@href, '{collection}.csv')]".format(collection=collection))
            )
        )
        self.log.info('Starting download of: {} - {}'.format(report_access_page_url, collection))
        elem.click()

        wait_for_any_file_in_folder(csv_download_folder_path, "csv")
        self.log.info('Download Finished.')

        df_report = pd.read_csv(get_most_recent_file_in_dir(csv_download_folder_path),
                                **kwargs)

        # if the dataframe is empty (the report had no data), raise an error
        if df_report.shape[0] == 0 and collection != 'schooladmins':
            raise ValueError('No data in report for user {} at url: {}'.format(
                self.username, interpret_report_url(self.base_url, application_page_url)))
        elif df_report.shape[0] == 0:
            warnings.warn("The 'schooladmins' collection has no data. Ensure that no school admins are shared.")

        self.driver.close()

        if not write_to_disk:
            shutil.rmtree(csv_download_folder_path)

        return df_report

    def download_google_accounts_manager_student_export(self):
        """ Downloads the Google Accounts Manager Student Export that includes student emails."""
        self.log.info('Starting student email download.')
        # set up the driver for execution
        self.driver = configure_selenium_chrome()
        self._login()

        # grab some cookies (need to do this here for _mkto_trk cookie)
        cookies_orig = self.driver.get_cookies()

        # open the Google Accounts Manager application page
        # note - clever applications like Google Accounts Manager have unique ids that are a part of their URL
        # note - we have to get the settings page of the Google Accounts Manager to get the cookie
        #  that we need in order to download the file
        self.driver.get('https://schools.clever.com/school/applications/50ca15a93bc2733956000007/settings')
        cookies_schools = self.driver.get_cookies()

        # we may need to get the gaprov.ops.clever.com to get a cookie in new versions of chromedriver
        self.driver.get('https://gaprov.ops.clever.com/')
        cookies_gaprov = self.driver.get_cookies()

        # create requests session to download report without need for file storage
        with requests.Session() as s:

            # transfer over a bunch of cookies to the requests session
            for cookie in cookies_orig:
                s.cookies.set(cookie['name'], cookie['value'])

            for cookie in cookies_schools:
                s.cookies.set(cookie['name'], cookie['value'])

            for cookie in cookies_gaprov:
                s.cookies.set(cookie['name'], cookie['value'])

            s.cookies.set('_gat', "1")
            s.cookies.set('_gat_globalTracker', "1")

            report_url = 'https://gaprov.ops.clever.com/reporting/student'

            # download with 10 retries on failure
            c = 0
            while True:
                download_response = s.get(report_url, stream=True)

                if download_response.ok:
                    df_report = pd.read_csv(io.StringIO(download_response.content.decode('utf-8')))
                else:
                    self.log.info('Download failed for report url: {}'.format(report_url))
                    self.log.info('Download status_code: {}'.format(download_response.status_code))
                    self.log.info('Retrying... Retry#: {}'.format(c+1))
                    if c >= 9:
                        raise ValueError('Unable to download report after multiple retries.')
                    # add some jitter to the requests
                    sleep_time = (1000 + randint(500)) / 1000
                    time.sleep(sleep_time)
                    c += 1
                    continue
                break
        self.driver.close()

        self.log.info('Student email download complete.')

        return df_report


