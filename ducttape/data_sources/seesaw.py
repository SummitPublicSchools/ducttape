from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import super
from builtins import int
from builtins import str
from future import standard_library
from future.utils import raise_with_traceback
standard_library.install_aliases()
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementNotVisibleException,
)
from selenium.webdriver.common.by import By
import pandas as pd
import calendar
from datetime import datetime
import email
import imaplib
import logging
import os
import glob
import re
import shutil
import time
from tempfile import mkdtemp

# local import
from ducttape.webui_datasource import WebUIDataSource
from ducttape.utils import (
    configure_selenium_chrome,
    interpret_report_url,
    wait_for_any_file_in_folder,
    get_most_recent_file_in_dir,
    delete_folder_contents,
    DriverBuilder,
    LoggingMixin,
    ZipfileLongPaths,
)
from ducttape.exceptions import (
    DuctTapeException,
    ReportNotReady,
    NoDataError,
    ReportNotFound,
    InvalidLoginCredentials,
)

SEESAW_DEFAULT_EXPORT_ENCODING = 'utf-8'
NUMBER_OF_RETRIES = 5
DEFAULT_REPORT_FIELDS = ["Classes", "Teachers", "Students", "Families", "Analytics"]

# bZ9<Rd66 - outlook password for reports@killinglyschools.org
# https://app.seesaw.me/#/district/district.da305f84-f939-4b10-ab31-2eb55bc1b8f3  -- homepage for killingly seesaw

class Seesaw(WebUIDataSource, LoggingMixin):
    """ Class for interacting with SchoolMint
    """

    def __init__(self, username, password, wait_time, hostname, temp_folder_path=None, headless=False, school_district=None):
        super().__init__(username, password, wait_time, hostname, temp_folder_path, headless)
        self.uri_scheme = 'https://'
        self.base_url = self.uri_scheme + self.hostname
        self.school_district = school_district

    def _login(self):
        """ Logs into the provided SchoolMint instance.
        """
        retries = 0
        while retries < NUMBER_OF_RETRIES:
            self.log.debug('Logging into Seesaw, at try {}: {}'.format(retries, self.base_url))
            self.driver.get(self.base_url + "/#/login?role=org_admin")
            # wait until login form available
            try:
                elem = WebDriverWait(self.driver, self.wait_time).until(EC.presence_of_element_located((By.ID, 'sign_in_email')))
                elem.clear()
                elem.send_keys(self.username)
                elem = self.driver.find_element_by_id("sign_in_password")
                elem.clear()
                elem.send_keys(self.password)
                elem.send_keys(Keys.RETURN)
                break
            except ElementNotVisibleException:
                retries += 1

        # check that login succeeded by looking for the 'Student Activity Report' button
        try:
            elem = WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[ng-if='showStudentActivityReportForDistrict']")))
        except TimeoutException:
            self.driver.close()
            raise InvalidLoginCredentials

    def download_url_report(self, report_url, temp_folder_name):
        return report_url

    def _click_student_activity_report(self):
        """
        Navigates the Seesaw User Interface and clicks on the "Show Student Activity Report For District"
        button to initiate a CSV export. The csv file is sent to the district's email.
        """
        try:
            self.log.info("Getting student activity report.")
            elem = self.driver.find_element_by_css_selector("[ng-if='showStudentActivityReportForDistrict']")
            elem.click()

            popup_elem = WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid=":student-activity-report-send-button"]'))
            )
            popup_elem.click()

            ok_elem = WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'MuiButton-label'))
            )
            ok_elem.click()
        except TimeoutException:
            self.driver.close()
            raise DuctTapeException

    def _get_csv_link_from_email(self, email_host, port_number, email_login, email_password):
        """
        Navigates the given email account to find the Seesaw email with a link to the report csv and
        returns that link.
        @param email_host: host site of email
        @param port_number: port number for connection
        @param email_login: username credential for login
        @param email_password: password credential for login
        @return: [str] the link to the csv file
        """
        # Email with csv link can take up to an hour to send. Retrying for 1 hour
        retries = 0
        while retries <= 15:
            imap_connection = imaplib.IMAP4_SSL(email_host, port_number)
            imap_connection.login(email_login, email_password)
            imap_connection.select()

            date = self._fetch_date()
            subject = f"Student Activity Report for {self.school_district} on {date}"
            logging.info(f"Searching for subject: {subject}")

            status, emails = imap_connection.search(None, f'(SUBJECT "{subject}")')
            if status != 'OK':
                if retries == 10:
                    raise ConnectionError
                else:
                    print("Sleeping for 4 minutes...")
                    retries += 1
                    time.sleep(240)
            else:
                break

        # Reset retry count for fetching link from emails
        retries = 0
        while retries <= NUMBER_OF_RETRIES:
            try:
                nums = emails[0].split()
                # Ensure we get the most recent email
                message_string = self._get_most_recent_email(imap_connection, nums)
                r = re.search("https:\/\/assets.seesaw.me.*.csv", message_string)

                link = r.group(0)
                return link
            except IndexError:
                if retries == NUMBER_OF_RETRIES:
                    raise NoDataError
                else:
                    retries += 1

    def _fetch_school_link_elements(self, report_list=DEFAULT_REPORT_FIELDS, home_suffix=None):
        if not home_suffix:
            home_url = self.driver.current_url
        else:
            home_url = self.base_url + home_suffix
            self.driver.get(home_url)

        elements = self.driver.find_elements_by_css_selector('[ng-repeat="school in districtInfo.schools.objects"]')
        print(len(elements))

        for i in range(len(elements)):
            e.click()
            for r in report_list:
                #tag_link = self.driver.find_element_by_link_text(r)
                tag_link = WebDriverWait(self.driver, self.wait_time).until(
                    EC.presence_of_element_located((By.LINK_TEXT, r))
                )
                tag_link.click()
                if r == "Analytics":
                    print(r)
            self.driver.get(home_url)

    def _navigate_tabs_and_download_csvs(self):
        pass

    def _fetch_date(self, date=None):
        """
        Helper function for returning the given date in "Day, Month, Date, Year" format
        @param date: The date to convert. If none is given, use today's date
        @return: [str] The date, in the format: "<Day-of-Week>, <Month> <Day>, <Year>"
        """
        if not date:
            date = datetime.today()

        day_of_week = calendar.day_name[date.weekday()]
        date_str = date.strftime("%B %d, %Y")
        return f"{day_of_week}, {date_str}"


    def _get_most_recent_email(self, imap_connection, numbers):
        """
        Helper for returning the most recent email in the list of emails given
        @param imap_connection: an IMAP4_SSL object
        @param numbers: a list of numbers that imap uses to fetch email messages
        @return: The most recent email message, as a raw string
        """
        timestamp = None
        most_recent_email = None
        for n in numbers:
            mail_object = imap_connection.fetch(n, '(RFC822)')
            message = email.message_from_bytes(mail_object[1][0][1])
            message_string = message.as_string()
            # Isolate timestamp that email was sent
            r = re.search("\n \d\d:\d\d:\d\d \+", message_string)
            if not timestamp or r.group(0) > timestamp:
                timestamp = r.group(0)
                most_recent_email = message_string
                logging.info(r.group(0) + " is the most recent as of now")
        return most_recent_email


    def _download_csv_from_link(self, link):
        """
        Downloads a csv from a link into a dataframe object
        @param link: The link to download
        @return: the dataframe object
        """
        df = pd.read_csv(link, encoding=SEESAW_DEFAULT_EXPORT_ENCODING, skiprow=1)
        return df


    def generate_student_activity_report_and_fetch_csv(self, email_host, port_number, email_login, email_password):
        """
        Log into the Seesaw UI and start a Student Activity csv export, then log into the district's email,
        get the URL of the csv file, and return a pandas DataFrame created from the CSV file's data.
        @param email_host: host site of email
        @param port_number: port number for connection
        @param email_login: username credential for login
        @param email_password: password credential for login
        @return: [DF] a pandas DataFrame object
        """
        # Log into Seesaw and start csv export
        self._login()
        self._click_student_activity_report()

        # Get the link of the CSV from the Seesaw email, then download it into a DataFrame
        link = self._get_csv_link_from_email(email_host, port_number, email_login, email_password)
        df = self._download_csv_from_link(link)
        return df
