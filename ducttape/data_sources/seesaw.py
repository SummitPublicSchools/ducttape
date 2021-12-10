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
    ElementNotVisibleException,
)
from selenium.webdriver.common.by import By
import pandas as pd
import calendar
from datetime import datetime, timedelta
import email
import imaplib
import logging
import os
import re
import time
from tempfile import mkdtemp

# local import
from ducttape.webui_datasource import WebUIDataSource
from ducttape.utils import LoggingMixin
from ducttape.exceptions import (
    DuctTapeException,
    NoDataError,
    InvalidLoginCredentials,
)

SEESAW_DEFAULT_EXPORT_ENCODING = 'utf-8'
NUMBER_OF_RETRIES = 5
DEFAULT_REPORT_FIELDS = ["Classes", "Teachers", "Students", "Families", "Analytics"]


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

    # Temporary definition for abstract function
    def download_url_report(self, report_url, temp_folder_name):
        return report_url

    def _click_student_activity_report(self):
        """
        Navigates the Seesaw User Interface and clicks on the "Show Student Activity Report For District"
        button to initiate a CSV export. The csv file is sent to the district's email.
        """
        try:
            logging.info("Getting student activity report.")
            elem = WebDriverWait(self.driver, self.wait_time).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[ng-if='showStudentActivityReportForDistrict']"))
            )
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
            if status != 'OK' or len(emails[0].split()) == 0:
                if retries == 15:
                    raise ConnectionError
                else:
                    logging.info("Sleeping for 4 minutes...")
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
        df = pd.read_csv(link, encoding=SEESAW_DEFAULT_EXPORT_ENCODING, skiprows=1)
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

    def fetch_school_link_tab_file(self, school_name, report_tab, home_suffix=None, start_date=None, end_date=None):
        """
        Given a school name and a report to download, navigate to that school's section and download the requested
        report, then return a pandas DataFrame with the report's information
        @param school_name: Name of school as it is displayed on the Seesaw home page
        @param report_tab: Name of tab to navigate to and download from
        @param home_suffix: URL suffix to start and end this navigation at. Default is usually the home page
        after login
        @param start_date: A start date for Analytics stats - only used if report_tab == Analytics
        @param end_date: An end date for Analytics stats - only used if report_tab == Analytics
        @return: a pandas DataFrame
        """
        if not home_suffix:
            home_url = self.driver.current_url
        else:
            home_url = self.base_url + home_suffix
            self.driver.get(home_url)

        school_element = self.driver.find_element_by_link_text(school_name)
        school_element.click()

        tag_link = WebDriverWait(self.driver, self.wait_time).until(
            EC.presence_of_element_located((By.LINK_TEXT, report_tab))
        )
        tag_link.click()
        # The Analytics tab has a different interface than the other tabs
        if report_tab == "Analytics":
            # Update start date and end date boxes if necessary
            if start_date is not None:
                datetime_start = datetime.strptime(start_date, '%Y%m%d')
                if datetime_start.date() >= datetime.today().date() - timedelta(days=1):
                    raise Exception("Start date must be on or before yesterday's date.")
                start_date_str = datetime_start.strftime("%m/%d/%Y")
                start_box = WebDriverWait(self.driver, self.wait_time).until(
                    EC.element_to_be_clickable((By.ID, 'start-datepicker'))
                )
                start_box.clear()
                start_box.send_keys(start_date_str)
                start_box.send_keys(Keys.RETURN)

            if end_date is not None:
                datetime_end = datetime.strptime(end_date, '%Y%m%d')
                if datetime_end.date() < datetime.now().date() - timedelta(days=1):
                    raise Exception("End date must be on or before yesterday's date.")
                elif start_date is not None and datetime_end.date() < datetime.strptime(start_date, '%Y%m%d').date():
                    raise Exception("End date must be the same or a later day than start date.")
                end_date_str = datetime_end.strftime("%m/%d/%Y")
                end_box = WebDriverWait(self.driver, self.wait_time).until(
                    EC.element_to_be_clickable((By.ID, 'end-datepicker'))
                )
                end_box.clear()
                end_box.send_keys(end_date_str)
                end_box.send_keys(Keys.RETURN)

            # Wait a few seconds for stats to update before downloading file
            logging.info("Waiting 5 seconds for stats to update before downloading Analytics file.")
            time.sleep(5)
            download_link = WebDriverWait(self.driver, self.wait_time).until(
                EC.element_to_be_clickable((By.LINK_TEXT, 'Download Stats'))
            )
            download_link.click()
        else:
            dropdown_element = WebDriverWait(self.driver, self.wait_time).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '[alt="Dropdown icon"]'))
            )
            dropdown_element.click()
            # List of elements in dropdown. Sometimes includes more than one option, so we search for Download CSV
            elements = self.driver.find_elements_by_css_selector('[ng-repeat="menuItem in dashboardGearMenuItems"]')
            for e in elements:
                if "Download CSV" in e.text:
                    e.click()
                    break

        retries = 0
        df = None
        filename = None
        while retries <= NUMBER_OF_RETRIES and df is None:
            try:
                for file in os.listdir(self.temp_folder_path):
                    if report_tab == "Analytics" and "Stats" in file:
                        filename = file
                        logging.info(f"Download file at: {self.temp_folder_path}/{file}")
                    elif report_tab.lower() in file:
                        filename = file
                        logging.info(f"Download file at: {self.temp_folder_path}/{file}")
                df = pd.read_csv(f"{self.temp_folder_path}/{filename}")
            except FileNotFoundError:
                if retries == NUMBER_OF_RETRIES:
                    raise FileNotFoundError("File not downloaded")
                time.sleep(10)
                retries += 1
        # Go back to original page so we can navigate to another school & tab if needed
        self.driver.get(home_url)
        # Delete file so it does not interfere with future downloaded files in the directory
        os.remove(f"{self.temp_folder_path}/{filename}")
        return df
