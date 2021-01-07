from ducttape.webui_datasource import WebUIDataSource
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from future.utils import raise_with_traceback
import pandas as pd
import time
from tempfile import mkdtemp
import shutil
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementNotVisibleException,
)

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
    NoDataError,
)

REPORT_GENERATION_WAIT = 10


class SummitLearning(WebUIDataSource, LoggingMixin):
    def __init__(self, username, password, wait_time, hostname='summitlearning.org', temp_folder_path=None,
                 headless=False, login_provider='google'):
        super().__init__(username, password, wait_time, hostname, temp_folder_path, headless)
        self.login_provider=login_provider
        self.uri_scheme = 'https://'
        self.base_url = self.uri_scheme + 'www.' + self.hostname

    def _login(self):
        if self.login_provider == 'google':
            login_url = self.base_url + '/auth/google_oauth2'
            self.driver.get(login_url)

            # the Google login screen has multiple versions - the 'Email' one
            # seems to be used when headless
            try:
                elem = self.driver.find_element_by_id('Email')
            except NoSuchElementException:
                elem = self.driver.find_element_by_id('identifierId')
            elem.clear()
            elem.send_keys(self.username)
            elem.send_keys(Keys.RETURN)

            # headless version of Google Login
            elem = WebDriverWait(self.driver, self.wait_time).until(
                EC.visibility_of_element_located((By.ID, 'password'))
            )
            # regular version of Google login
            if elem.tag_name == 'div':
                elem = WebDriverWait(self.driver, self.wait_time).until(
                    EC.element_to_be_clickable((By.NAME, 'password')))
            elem.send_keys(self.password)
            elem.send_keys(Keys.RETURN)

        # wait for the destination page to fully load
        WebDriverWait(self.driver, self.wait_time).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'app-teacher')))

    def download_url_report(self, report_url, write_to_disk=None, **kwargs):
        """ Downloads a Summit Learning report at a URL that triggers a CSV download

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

        if write_to_disk:
            csv_download_folder_path = write_to_disk
        else:
            csv_download_folder_path = mkdtemp()
        self.driver = DriverBuilder().get_driver(csv_download_folder_path, self.headless)
        self._login()

        self.log.debug('Getting report page at: {}'.format(report_download_url))
        self.driver.get(report_download_url)

        self.log.debug('Starting download of: '.format(report_download_url))

        wait_for_any_file_in_folder(csv_download_folder_path, "csv")
        self.log.debug('Download Finished.')

        df_report = pd.read_csv(get_most_recent_file_in_dir(csv_download_folder_path),
                                  **kwargs)

        # if the dataframe is empty (the report had no data), raise an error
        if df_report.shape[0] == 0:
            raise NoDataError('No data in report for user {} at url: {}'.format(
                self.username, interpret_report_url(self.base_url, report_url)))

        self.driver.close()

        if not write_to_disk:
            shutil.rmtree(csv_download_folder_path)

        return df_report

    def _set_dl_academic_year(self, academic_year):
        """Sets the academic year to download the reports from

        Args:
            academic_year (string): The academic year that should be selected. Use the format shown in the
                Summit Learning interface. Example: '2016-2017'

        :return: True if function succeeds
        """
        # The UI uses a '–' instead of a '-'. We'll make a convenience replacement
        academic_year = academic_year.replace('-', '–')

        self.log.debug('Changing academic year to: {}'.format(academic_year))

        # open the menu to select the academic year
        elem = WebDriverWait(self.driver, self.wait_time).until(
            EC.element_to_be_clickable((By.ID, 'academic-year-selector')))
        elem.click()

        # select the appropriate year
        try:
            year_xpath = "//*[@id='academic-year-selector']/parent::div//a[contains(text(),'{}')]".format(
                academic_year)
            elem = self.driver.find_element_by_xpath(year_xpath)
            elem.click()
        except NoSuchElementException as e:
            self.driver.save_screenshot('cannot_find_year.png')
            message = (
                ' Check that the academic_year variable is valid. '
                'Passed value for academic_year: {}'
            ).format(academic_year)

            raise_with_traceback(type(e)(str(e) + message))

        return True

    def check_dl_academic_year(self, academic_year):
        """Checks that the academic year is set as expected in the UI."""
        # The UI uses a '–' instead of a '-'. We'll make a convenience replacement
        academic_year = academic_year.replace('-', '–')

        elem = self.driver.find_element_by_xpath("//*[@id='academic-year-selector']/parent::div//button")

        if academic_year in elem.text:
            return True
        else:
            return False

    def download_site_data_download(self, dl_heading, site_id, academic_year, report_generation_wait=REPORT_GENERATION_WAIT,
                                write_to_disk=None, **kwargs):
        if write_to_disk:
            csv_download_folder_path = write_to_disk
        else:
            csv_download_folder_path = mkdtemp()
        self.driver = DriverBuilder().get_driver(csv_download_folder_path, self.headless)
        self._login()

        dl_page_url = "{base_url}/sites/{site_id}/data_downloads/".format(
            base_url=self.base_url,
            site_id=site_id
        )

        self.driver.get(dl_page_url)

        self._set_dl_academic_year(academic_year)

        if not self.check_dl_academic_year(academic_year):
            raise ValueError("Academic Year not correctly set")

        # start the CSV generation process
        download_button_xpath = "//h3[contains(text(), '{dl_heading}')]/parent::div/parent::div//a[contains(text(), '{button_text}')]"

        # try to find the "Download CSV" button - old version of the interface
        old_interface = False
        try:
            elem = self.driver.find_element_by_xpath(download_button_xpath.format(dl_heading=dl_heading,
                                                                             button_text='Download CSV'))
            old_interface = True
            self.log.info("'Download CSV' interface detected.")
            elem.click()
        # if it's not there, it may have changed to a "Refresh" button
        except NoSuchElementException as e:
            pass

        # try to find the "Generate CSV" button - new version of the interface

        if not old_interface:
            gen_button_xpath = "//h3[contains(text(), '{dl_heading}')]/parent::div/parent::div//button[contains(text(), '{button_text}')]"
            try:
                elem = self.driver.find_element_by_xpath(gen_button_xpath.format(dl_heading=dl_heading,
                                                                                 button_text='Generate CSV'))
                self.log.info("'Generate CSV' interface detected.")
                elem.click()
            # if it's not there, it may have changed to a "Refresh" button
            except NoSuchElementException as e:
                elem = self.driver.find_element_by_xpath(gen_button_xpath.format(dl_heading=dl_heading,
                                                                                 button_text='Refresh'))
                elem.click()

        # wait for the refresh command to be issued
        time.sleep(1)

        # wait for the report to be available and download it
        self.log.info('Starting download of report "{}" for site_id "{}"'.format(dl_heading, site_id))

        dl_button_xpath = "//h3[contains(text(), '{dl_heading}')]/parent::div/parent::div//a[contains(text(), 'Download')]"
        try:
            elem = WebDriverWait(self.driver, report_generation_wait).until(
                EC.presence_of_element_located((By.XPATH, dl_button_xpath.format(dl_heading=dl_heading)))
            )
            elem.click()
        # if the download is not ready, refresh the page and try one more time
        except TimeoutException:
            self.driver.refresh()
            elem = WebDriverWait(self.driver, report_generation_wait).until(
                EC.presence_of_element_located((By.XPATH, dl_button_xpath.format(dl_heading=dl_heading)))
            )
            elem.click()

        wait_for_any_file_in_folder(csv_download_folder_path, "csv")
        self.log.debug('Download Finished.')

        df_report = pd.read_csv(get_most_recent_file_in_dir(csv_download_folder_path),
                                **kwargs)

        # if the dataframe is empty (the report had no data), raise an error
        if df_report.shape[0] == 0:
            raise NoDataError('No data in report "{}" for site_id "{}"'.format(
                dl_heading, site_id))

        self.driver.close()

        if not write_to_disk:
            shutil.rmtree(csv_download_folder_path)

        return df_report
