import pandas as pd
import time
import shutil

from deprecated import deprecated
from ducttape.webui_datasource import WebUIDataSource
from future.utils import raise_with_traceback
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from tempfile import mkdtemp
from typing import Optional

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

REPORT_GENERATION_WAIT_CSV = 10
REPORT_GENERATION_WAIT_ZIP = 60


class SummitLearning(WebUIDataSource, LoggingMixin):
    def __init__(self, username, password, wait_time, hostname='summitlearning.org', temp_folder_path=None,
                 headless=False, login_provider='google'):
        super().__init__(username, password, wait_time, hostname, temp_folder_path, headless)
        self.login_provider = login_provider
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

        wait_for_any_file_in_folder(csv_download_folder_path, 'csv')
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

    # TODO: Add a docstring to this function
    # TODO: update this deprecated reason as appropriate
    @deprecated(reason='This is replaced by download_csv_site_data_download, download_zip_site_data_download,'
                       'or other convenience functions like...')
    def download_site_data_download(self, dl_heading, site_id, academic_year,
                                    report_generation_wait=REPORT_GENERATION_WAIT_CSV,
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
                try:
                    elem = self.driver.find_element_by_xpath(gen_button_xpath.format(dl_heading=dl_heading,
                                                                                     button_text='Refresh'))
                    elem.click()
                # if we don't have 'refresh' or 'generate', we have 'Download' button can can proceed to next step
                except NoSuchElementException as e:
                    pass

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

    def _download_site_data_download(self,
                                     dl_heading: str,
                                     site_id: int,
                                     academic_year: str,
                                     file_name: str,
                                     report_generation_wait: int,
                                     file_type: str,
                                     file_path: str,
                                     date: Optional[str] = None) -> str:
        """
        Generates and downloads report files from the Summit Learning Data Downloads web page.

        :param dl_heading: The title of a report on the Summit Learning Data Downloads page. Exclude the
            academic year. Example: 'Grades for Currently Enrolled Students (By Student/Course)'
        :param site_id: The id for the school for which the report should be downloaded. Get this from the
            URL of the data download page. Example: 3650
        :param academic_year: The academic year for which to download the report. This should match the
            format of the year in the school year selector drop down menu in the upper right hand
            corner of the Data Downloads page. Example: 2021-22
        :param report_generation_wait: When the report requires a 'Generate' button to be clicked, the number
            of seconds to wait for the report to be generated. Longer times may be needed for schools with
            more students.
        :param file_type: Options: 'csv' or 'zip'
        :param file_path: The path where the downloaded file should be stored.
        :param date: A string in the format 'YYYY-MM-DD'. This only applies to reports that are generated
            on a per-date basis.
        :return: The file path where the downloaded file was stored
        """
        download_folder_path = mkdtemp()

        if file_type not in ['csv', 'zip']:
            raise ValueError('File format must be zip or csv')

        self.driver = DriverBuilder().get_driver(download_folder_path, self.headless)
        self._login()

        dl_page_url = "{base_url}/sites/{site_id}/data_downloads/".format(
            base_url=self.base_url,
            site_id=site_id
        )

        self.driver.get(dl_page_url)

        self._set_dl_academic_year(academic_year)

        if not self.check_dl_academic_year(academic_year):
            raise ValueError("Academic Year not correctly set")

        # start the ZIP generation process
        download_button_xpath = "//h3[contains(text(), '{dl_heading}')]/parent::div/parent::div//a[contains(text(), '{button_text}')]"

        gen_button_xpath = "//h3[contains(text(), '{dl_heading}')]/parent::div/parent::div//button[contains(text(), '{button_text}')]"
        try:
            if file_type == 'zip':
                elem = self.driver.find_element_by_xpath(gen_button_xpath.format(dl_heading=dl_heading,
                                                                                 button_text='Generate Reports'))
                self.log.info("'Generate Reports' interface detected.")
                elem.click()
            if file_type == 'csv:':
                elem = self.driver.find_element_by_xpath(download_button_xpath.format(dl_heading=dl_heading,
                                                                                      button_text='Download CSV'))
                old_interface = True
                self.log.info("'Download CSV' interface detected.")
                elem.click()
        # if it's not there, it may have changed to a "Refresh" button
        except NoSuchElementException as e:
            try:
                elem = self.driver.find_element_by_xpath(gen_button_xpath.format(dl_heading=dl_heading,
                                                                                 button_text='Refresh'))
                elem.click()
            # if we don't have 'refresh' or 'generate', we have 'Download' button can can proceed to next step
            except NoSuchElementException as e:
                pass

        # wait for the refresh command to be issued
        time.sleep(report_generation_wait)

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

        wait_for_any_file_in_folder(download_folder_path, file_type)
        downloaded_file_path = get_most_recent_file_in_dir(download_folder_path)
        shutil.copyfile(downloaded_file_path, f"{file_path}/{file_name}")
        return f"{file_path}/{file_name}"

    def download_csv_site_data_download(self,
                                        dl_heading: str,
                                        site_id: int,
                                        academic_year: str,
                                        file_name: str,
                                        report_generation_wait: int = REPORT_GENERATION_WAIT_CSV,
                                        file_path: Optional[str] = None,
                                        date: Optional[str] = None,
                                        ) -> pd.DataFrame:
        # TODO: Finish filling out the param descriptions for this docstring
        # if file path not provided, create temporary directory to store file in, which is passed to protected function;
        # temp directory deleted at end of this function
        """
        Returns a pandas dataframe of a CSV-formatted report from the Summit Learning Data Downloads web page.

        Some of the reports on the Summit Learning Data Download page return CSVs and others return zip
        files. This function applies to those reports that return a CSV. These reports are typically
        identifiable as those that have a 'Generate CSV' button. As of 2022-02-02, the CSV reports are:
        * Grades for Currently Enrolled Students (By Student/Course)
        * Grades for Currently Enrolled Students (By Student)
        * Grades for Unenrolled Students (By Student/Course)
        * Grades by Specific Date for Currently Enrolled Students (By Student/Course)
        * Grades by Specific Date for Unenrolled Students (By Student/Course)
        * Student Mentoring Data for Currently Enrolled Students

        :param dl_heading:
        :param site_id:
        :param academic_year:
        :param report_generation_wait:
        :param file_path:
        :param date: A string in the format 'YYYY-MM-DD'. This only applies to reports that are generated
            on a per-date basis.
        :return: A pandas dataframe of the data downloaded in the CSV report
        """
        # TODO: Write this function. It should call _download_site_data_download as part of it

        self._download_site_data_download(dl_heading=dl_heading, site_id=site_id, academic_year=academic_year,
                                          file_name=file_name, report_generation_wait=REPORT_GENERATION_WAIT_CSV, file_type='csv',
                                          file_path=file_path)
        # moved down here
        df_report = pd.read_csv(get_most_recent_file_in_dir(file_path),
                                **kwargs)

        # if the dataframe is empty (the report had no data), raise an error
        if df_report.shape[0] == 0:
            raise NoDataError('No data in report "{}" for site_id "{}"'.format(
                dl_heading, site_id))

        self.driver.close()

        return df_report

    def download_zip_site_data_download(self,
                                        dl_heading: str,
                                        site_id: int,
                                        academic_year: str,
                                        file_name: str,
                                        file_path: Optional[str] = None,
                                        report_generation_wait: int = REPORT_GENERATION_WAIT_ZIP
                                        ) -> str:
        # TODO: Finish filling out the param descriptions for this docstring
        # should be straightforward, just call protected function and have it return file path after download
        """
        Generates and downloads a zip-formatted report from the Summit Learning Data Downloads web page.

        Some of the reports on the Summit Learning Data Download page return CSVs and others return zip
        files. This function applies to those reports that return a zip file. These reports are typically
        identifiable as those that have a 'Generate Reports' button. As of 2022-02-02, the zip reports are:
        * Grade-Specific Academic Data Reports
        * Subject-Specific Academic Data Reports
        :param dl_heading:
        :param site_id:
        :param academic_year:
        :param report_generation_wait:
        :param file_path:
        :return: The file path of the downloaded zip file
        """
        # TODO: Write this function. It should call _download_site_data_download as part of it
        return self._download_site_data_download(dl_heading=dl_heading, site_id=site_id, academic_year=academic_year,
                                                 file_name=file_name, report_generation_wait=REPORT_GENERATION_WAIT_ZIP, file_type='zip',
                                                 file_path=file_path)
