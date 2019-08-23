from ducttape.webui_datasource import WebUIDataSource
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import pandas as pd
from tempfile import mkdtemp
import shutil

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

            elem = WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located((By.ID, 'identifierId')))
            elem.clear()
            elem.send_keys(self.username)
            elem.send_keys(Keys.RETURN)

            elem = WebDriverWait(self.driver, self.wait_time).until(
                EC.visibility_of_element_located((By.NAME, 'password')))
            elem.send_keys(self.password)
            elem.send_keys(Keys.RETURN)

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
