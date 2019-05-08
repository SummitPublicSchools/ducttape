from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
import pandas as pd

# local import
from ducttape.webui_datasource import WebUIDataSource
from ducttape.utils import (
    configure_selenium_chrome,
    interpret_report_url,
    wait_for_any_file_in_folder,
    get_most_recent_file_in_dir,
    delete_folder_contents,
    DriverBuilder,
)


class Mealtime(WebUIDataSource):
    """ Class for interacting with the web ui of Mealtime
    """

    def __init__(self, username, password, wait_time, hostname, temp_folder_path, headless=False):
        super().__init__(username, password, wait_time, hostname, temp_folder_path, headless)
        self.uri_scheme = 'https://'
        self.base_url = self.uri_scheme + self.hostname

    def _login(self):
        """ Logs into the provided Mealtime instance.
        """
        self.driver.get(self.base_url + '/Base/SignIn.aspx')
        elem = self.driver.find_element_by_id("username")
        elem.clear()
        elem.send_keys(self.username)
        elem = self.driver.find_element_by_id("password")
        elem.send_keys(self.password)
        elem.send_keys(Keys.RETURN)

    def download_url_report(self, report_url, temp_folder_name):
        """ Downloads a MealTime report.

        Args:
            report_url (string): Information pertaining to the path and query
                string for the report whose access is desired. Any filtering
                that can be done with a stateful URL should be included.
            temp_folder_name (string): The name of the folder in which this
                specific report's download files should be stored.

        Returns: A Pandas DataFrame of the report contents.
        """
        csv_download_folder_path = self.temp_folder_path + '/' + temp_folder_name
        # set up the driver for execution
        self.driver = DriverBuilder().get_driver(csv_download_folder_path, self.headless)
        self._login()

        # get the report url
        self.driver.get(interpret_report_url(self.base_url, report_url))

        # select the download format (csv) and execute
        export_format_select = Select(self.driver.find_element_by_id('ctl00_ctl00_MainContent_reportViewer_ctl01_ctl05_ctl00'))
        try:
            export_format_select.select_by_value('CSV')
            dl_type = 'csv'
        except NoSuchElementException:
            export_format_select.select_by_value('EXCELNoHeader')
            dl_type = 'xls'
        self.driver.find_element_by_id('ctl00_ctl00_MainContent_reportViewer_ctl01_ctl05_ctl01').click()

        # wait until file has downloaded to close the browser. We can do this
        # because we delete the file before we return it, so the temp dir should
        # always be empty when this command is run
        # TODO add a try/except block here
        wait_for_any_file_in_folder(csv_download_folder_path, dl_type)

        # remove the header rows
        #xlrd.open_workbook(utils.get_most_recent_file_in_dir(csv_download_folder_path), formatting_info=False)

        if dl_type == 'csv':
            report_df = pd.read_csv(get_most_recent_file_in_dir(csv_download_folder_path),
                                      header=2)
        else:
            report_df = pd.read_excel(get_most_recent_file_in_dir(csv_download_folder_path),
                                      header=3)

        # delete any files in the mealtime temp folder; we don't need them now
        # TODO: move this out of this function. It should happen as cleanup once
        # the whole DAG has completed
        delete_folder_contents(csv_download_folder_path)

        self.driver.close()

        # if the dataframe is empty (the report had no data), raise an error
        if report_df.shape[0] == 0:
            raise ValueError('No data in report for user {} at url: {}'.format(self.username, interpret_report_url(self.base_url, report_url)))

        return report_df
