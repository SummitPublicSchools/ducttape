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
import time
import datetime
import os
import glob
import re
import shutil
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
    ReportNotReady,
    NoDataError,
    ReportNotFound,
    InvalidLoginCredentials,
)

NUMBER_OF_RETRIES = 3


class Panorama(WebUIDataSource, LoggingMixin):
    """ Class for interacting with Panorama
    """

    def __init__(self, username, password, district_suffix, wait_time=30, hostname='secure.panoramaed.com', temp_folder_path=None, headless=False):
        super().__init__(username, password, wait_time, hostname, temp_folder_path, headless)
        self.district_suffix = district_suffix
        self.uri_scheme = 'https://'
        self.base_url = self.uri_scheme + self.hostname

    def _login(self):
        """ Logs into the provided Panorama instance.
        """
        count = 0
        while count < NUMBER_OF_RETRIES:
            self.log.debug('Logging into Panorama at, try {}: {}'.format(count, self.base_url))
            self.driver.get(self.base_url + "/lognin")
            # wait until login form available
            try:
                elem = WebDriverWait(self.driver, self.wait_time).until(EC.presence_of_element_located((By.ID, 'user_email')))
                elem.clear()
                elem.send_keys(self.username)
                elem = self.driver.find_element_by_id("user_password")
                elem.send_keys(self.password)
                elem.send_keys(Keys.RETURN)
                break
            except ElementNotVisibleException:
                count += 1

        # check that login succeeded by looking for the 'Results' section
        try:
            elem = WebDriverWait(self.driver, self.wait_time).until(EC.presence_of_element_located((By.CLASS_NAME, 'results-header')))
        except TimeoutException:
            self.driver.close()
            raise InvalidLoginCredentials

    def download_panorama_report_file(self, report_id):
        """
        Downloads a report from the Admin page and returns it as a pandas DataFrame
        param report_id: The id of the report to download.
        :returns: pandas.DataFrame object
        """
        self.driver.get(self.base_url + f"/{self.district_suffix}/understand")
        elem = self.driver.find_element_by_xpath("//span [contains( text(), 'Admin')]")
        elem.click()
        time.sleep(5)

        elements = self.driver.find_elements_by_xpath('//td [@class = "download-cell"]')
        for element in elements:
            child = element.find_element(By.XPATH, ".//a")
            if report_id in child.get_attribute('data-path'):
                child.click()
                break

        time.sleep(10)
        file = os.listdir(self.temp_folder_path)[0]
        file_path = f"{self.temp_folder_path}/{file}"
        df = pd.read_csv(file_path)
        os.remove(file_path)
        return df

    def download_url_report(self, report_url):
        """
        """
        return