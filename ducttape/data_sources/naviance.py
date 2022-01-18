import logging
import os
import pandas as pd
import requests
import shutil
import time

# selenium imports
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import ElementNotInteractableException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

# external imports
from tempfile import mkdtemp
from urllib.parse import urlparse
from urllib.parse import parse_qs

# intra-packages imports
from ducttape.webui_datasource import WebUIDataSource
from ducttape.utils import (
    configure_selenium_chrome,
    interpret_report_url,
    wait_for_any_file_in_folder,
    get_most_recent_file_in_dir,
    delete_folder_contents,
    DriverBuilder,
)

from ducttape.exceptions import (
    InvalidLoginCredentials,
    ReportNotFound,
    NoDataError,
)

# create logger
LOGGER = logging.getLogger('sps-automation.data_sources.naviance')
NAVIANCE_LOGIN_HOSTNAME = 'id.naviance.com'


class Naviance(WebUIDataSource):
    """ Class for interacting with the web ui of Naviance
    """

    def __init__(self, username, password, wait_time, profile_id, profile_type='district',
                 hostname='succeed.naviance.com', temp_folder_path=None, headless=False,
                 sso_user=None, sso_password=None):
        """

        :param username:
        :param password:
        :param wait_time:
        :param profile_id: The Naviance profile id to use. This can be found by going to
            https://id.naviance.com/naviance-profiles?show, inspecting the button for the
            particular profile, and finding the number at the end of the URL (e.g.
            2017111)
        :param hostname:
        :param temp_folder_path:
        :param headless:
        """
        self.logger = logging.getLogger('sps-automation.data_sources.naviance.Naviance')
        self.logger.debug('creating an instance of Naviance')
        super().__init__(username, password, wait_time, hostname, temp_folder_path, headless)
        self.uri_scheme = 'https://'
        self.base_url = self.uri_scheme + self.hostname
        self.profile_id = profile_id
        self.sso_user = sso_user
        self.sso_password = sso_password

        # TODO: Make this more robust
        if profile_type not in ['district']:
            raise ValueError('Invalid profile type')

        self.profile_type = profile_type
        self.session = requests.Session()

    def _login(self):
        """ Logs into the provided Naviance instance.
        """
        self.logger.debug('logging in to Naviance with username: {}'.format(self.username))
        self.driver.get(self.uri_scheme + NAVIANCE_LOGIN_HOSTNAME)
        WebDriverWait(self.driver, self.wait_time).until(EC.title_is("Sign in"))

        # click "Sign in with Naviance ID" to load actual login screen
        button = self.driver.find_element_by_xpath('//a[@href="/login"]')
        button.click()
        WebDriverWait(self.driver, self.wait_time).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "auth0-lock-submit"))
        )

        sso = False
        input_form = self.driver.find_element_by_name("email")
        input_form.clear()
        input_form.send_keys(self.username)

        try:
            input_form = self.driver.find_element_by_name("password")
            input_form.clear()
            input_form.send_keys(self.password)
        except ElementNotInteractableException:
            sso = True

        button = self.driver.find_element_by_class_name("auth0-lock-submit")
        button.click()

        if sso:
            input_form = WebDriverWait(self.driver, self.wait_time).until(
                EC.element_to_be_clickable((By.NAME, "identifier"))
            )
            input_form.clear()
            input_form.send_keys(self.sso_user)

            button = self.driver.find_element_by_class_name("VfPpkd-vQzf8d")
            button.click()

            input_form = WebDriverWait(self.driver, self.wait_time).until(
                EC.element_to_be_clickable((By.NAME, "password"))
            )
            input_form.clear()
            input_form.send_keys(self.sso_password)

            button = self.driver.find_element_by_class_name("VfPpkd-vQzf8d")
            button.click()

        try:
            WebDriverWait(self.driver, self.wait_time).until(
                EC.title_is("Profiles") or
                # TODO - expand this to work with school logins
                EC.title_is("Naviance District Edition")
            )

            if EC.title_is("Profiles"):
                self.driver.get(f'https://id.naviance.com/naviance-profiles/switch/{self.profile_id}')
        except TimeoutException:
            pass

        WebDriverWait(self.driver, self.wait_time).until(
            EC.title_is("Naviance District Edition")
        )

        # export and save session cookie
        cookie = self.driver.get_cookie("sess")
        self.session.cookies.set(cookie.get("name"), cookie.get("value"))

    def download_url_report(self, report_url, customization_params=None, write_to_disk=None, **pandas_read_csv_kwargs):
        """ Downloads a Naviance report.

        Args:
            report_url (string): Information pertaining to the path and query
                string for the report whose access is desired. Any filtering
                that can be done with a stateful URL should be included.
            temp_folder_name (string): The name of the folder in which this
                specific report's download files should be stored.

        Returns: A Pandas DataFrame of the report contents.
        """
        report_download_url = interpret_report_url(
            self.uri_scheme + 'succeed.naviance.com', report_url)
        
        report_download_csv_url = f'{report_download_url}&format=csv'

        # get report id from url
        parsed_url = urlparse(report_download_url)
        report_instance_id = parse_qs(parsed_url.query)['report_instance_id'][0]

        if write_to_disk:
            csv_download_folder_path = write_to_disk
        else:
            csv_download_folder_path = mkdtemp()
        self.driver = DriverBuilder().get_driver(csv_download_folder_path, self.headless)
        self._login()

        if "customize" in report_url:
            if customization_params is None:
                raise Exception("There must be at least one custom parameter for customization.")
            self.driver.get(report_url)
            time.sleep(3)
            for param in customization_params:
                select = Select(self.driver.find_element_by_name(param))
                select.select_by_value(customization_params[param])

            while True:
                try:
                    button = self.driver.find_element_by_class_name('submit-selected')
                    button.click()
                except:
                    break

            download_button = WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located((By.ID, 'csv'))
            )
            download_button.click()

        else:
            self.driver.get(report_download_csv_url)

        self.logger.debug('Getting report page at: {}'.format(report_download_url))
        

        self.logger.debug('Starting download of: '.format(report_download_url))

        wait_for_any_file_in_folder(csv_download_folder_path, "csv")
        self.logger.debug('Download Finished.')

        df_report = pd.read_csv(get_most_recent_file_in_dir(csv_download_folder_path),
                                **pandas_read_csv_kwargs)

        # if the dataframe is empty (the report had no data), raise an error
        if df_report.shape[0] == 0:
            raise NoDataError('No data in report for user {} at url: {}'.format(
                self.username, interpret_report_url(self.base_url, report_url)))

        self.driver.close()

        if not write_to_disk:
            shutil.rmtree(csv_download_folder_path)

        return df_report

    def download_student_outcomes_report(self, start_class_year_grade=0, end_class_year_grade=0,
                                         zone=0, school=0, student_group=0):
        """

        :param start_class_year_grade:
        :param end_class_year_grade:
        :param zone:
        :param school: (e.g. 182120USPU)
        :param student_group:
        :return:
        """
        report_id = 1323
        report_url = f"{self.base_url}/{self.profile_type}/reporting-framework/reports/view" \
                     f"?report_instance_id={report_id}"
        customization_params = {
            "settings_custom[StartClassYear]": start_class_year_grade,
            "settings_min[StartClassYear]": 0,
            "settings_max[StartClassYear]": 0,
            "settings_custom[EndClassYear]": end_class_year_grade,
            "settings_min[EndClassYear]": 0,
            "settings_max[EndClassYear]": 0,
            "settings_custom[Zone]": zone,
            "settings_min[Zone]": 0,
            "settings_max[Zone]": 0,
            "settings_custom[School]": school,
            "settings_min[School]": 0,
            "settings_max[School]": 0,
            "settings_custom[StudentGroup]": student_group,
            "settings_min[StudentGroup]": 0,
            "settings_max[StudentGroup]": 0,
        }

        return self.download_url_report(report_url=report_url,
                                        customization_params=customization_params)

    def download_data_export(self, data_type: str, start_year: str = None, end_year: str = None, sleep=30):
        url = 'https://succeed.naviance.com/district/setupmain/export.php'

        self.driver.get(url)
        export_button = WebDriverWait(self.driver, self.wait_time).until(
            EC.presence_of_element_located((By.NAME, 'exportData'))
        )

        if start_year:
            select = Select(self.driver.find_element_by_name('start_year'))
            select.select_by_value(start_year)

        if end_year:
            select = Select(self.driver.find_element_by_name('end_year'))
            select.select_by_value(end_year)

        select = Select(self.driver.find_element_by_name('type'))
        select.select_by_value(data_type)

        export_button.click()
        time.sleep(sleep)
        retries = 0
        while retries <= 20:
            try:
                filename = os.listdir(self.temp_folder_path)[0]
                df = pd.read_csv(f"{self.temp_folder_path}/{filename}")
                os.remove(f"{self.temp_folder_path}/{filename}")
                return df
            except IndexError as e:
                if retries == 20:
                    raise IndexError(e)
                else:
                    retries += 1
                    time.sleep(30)

    def download_data_export_by_encoded_params(self, encoded_params, write_to_disk=None, **pandas_read_csv_kwargs):
        if write_to_disk:
            csv_download_folder_path = write_to_disk
        else:
            csv_download_folder_path = mkdtemp()
        self.driver = DriverBuilder().get_driver(csv_download_folder_path, self.headless)
        self._login()

        # time.sleep(5)

        url = 'https://succeed.naviance.com/district/setupmain/exportdata.php'
        params = parse_qs(urlparse(f"{url}?&{encoded_params}").query)
        print(params)
        response = self.session.post(
            url=url,
            params=params
        )

        print(f"\n#################")
        print(response)
        print(response.headers)
        # print(response.json())
        print("######")
        # time.sleep(30)




