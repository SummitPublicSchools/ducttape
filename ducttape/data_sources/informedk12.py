# selenium imports
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

# external imports
import pandas as pd
import time
import logging

# intra-packages imports
from ducttape.webui_datasource import WebUIDataSource
from ducttape.utils import configure_selenium_chrome, interpret_report_url, wait_for_any_file_in_folder, \
                    get_most_recent_file_in_dir, delete_folder_contents

# create logger
LOGGER = logging.getLogger('sps-automation.data_sources.informedk12')


class InformedK12(WebUIDataSource):
    """ Class for interacting with the web ui of Informed K12
    """

    def __init__(self, username, password, wait_time, hostname, temp_folder_path):
        super().__init__(username, password, wait_time, hostname, temp_folder_path)
        self.uri_scheme = 'https://'
        self.base_url = self.uri_scheme + self.hostname
        self.logger = logging.getLogger('sps-automation.data_sources.chalkschools.InformedK12')
        self.logger.debug('creating an instance of InformedK12')

    def _login(self):
        """ Logs into the provided Informed K12 instance.
        """
        self.logger.debug('logging in to Informed K12 Schools with username: {}'.format(self.username))
        self.driver.get(self.base_url)
        elem = self.driver.find_element_by_id("session_email")
        elem.clear()
        elem.send_keys(self.username)
        elem = self.driver.find_element_by_id("session_password")
        elem.send_keys(self.password)
        elem.send_keys(Keys.RETURN)

    def download_url_report(self, report_url, temp_folder_name):
        """ Downloads an Informed K12 report.

        Args:
            report_url (string): Information pertaining to the path and query
                string for the report whose access is desired. Any filtering
                that can be done with a stateful URL should be included.
            temp_folder_name (string): The name of the folder in which this
                specific report's download files should be stored.

        Returns: A Pandas DataFrame of the report contents.
        """
        count = 0
        while True:
            try:
                # WebDriverException - except
                csv_download_folder_path = self.temp_folder_path + '/' + temp_folder_name
                # set up the driver for execution
                self.driver = configure_selenium_chrome(csv_download_folder_path)
                self._login()

                time.sleep(2)
                #self.driver.get(self.base_url)

                # get the report url
                self.driver.get(interpret_report_url(self.base_url, report_url))

                # select all responses
                # get the report url
                #self.driver.get(interpret_report_url(self.base_url, report_url))

                # check to see if there are no submissions. If so, abort by exception
                try:
                    self.driver.find_element_by_xpath("//h2[contains(text(), 'No submissions')]")
                    self.driver.close()
                    raise ValueError('No data in report for user {} at url: {}'.format(self.username, interpret_report_url(self.base_url, report_url)))
                except NoSuchElementException:
                    # We actually don't want to find this.
                    pass

                # wait until we have rows in the responses data table before starting to
                # look for results
                try:
                    elem = WebDriverWait(self.driver, self.wait_time).until(EC.presence_of_element_located((By.XPATH, "//*[@class='responses-table']/table/thead/tr[1]/*[@class='checkboxes']/input")))
                except TimeoutException:
                    raise

                # select all
                elem.click()

                # check to see if a new link populates to 'select all filtered submissions" (happens if more than 50 submissions)
                try:
                    elem = self.driver.find_element_by_xpath("//*[@class='responses-bulk-actions']/*[@class='select-link']")
                    elem.click()
                except NoSuchElementException():
                    pass

                # click download
                elem = self.driver.find_element_by_xpath("//*[contains(text(), 'Download') and @class='hidden-xs']")
                elem.click()

                # click 'As a spreadsheet'
                elem = self.driver.find_element_by_xpath("//*[@class='dropdown-menu dropdown-menu-right']//*[contains(text(), 'As a spreadsheet')]")
                elem.click()

                # activate the menu that allows 'select all'
                try:
                    # the following elem selection fails b/c is moves, so we time.sleep to let it load first
                    time.sleep(0.5)
                    elem = WebDriverWait(self.driver, self.wait_time).until(EC.visibility_of_element_located((By.XPATH, "//*[@class='dropdown-toggle']/*[contains(text(), 'columns')]/i")))
                    elem.click()
                except TimeoutException:
                    # TODO
                    raise

                # click on 'select all'
                elem = self.driver.find_element_by_xpath("//*[@class='dropdown-menu dropdown-menu-right']//*[contains(text(), 'Select all')]")
                elem.click()

                # wait a moment for the info to populate
                time.sleep(2)

                # click download
                # elem = self.driver.find_element_by_xpath(
                #     "//*[@class='btn btn-primary' and contains(text(), 'Download')]")
                # elem.click()
                #
                # time.sleep(1)
                # try:
                #     elem = self.driver.find_element_by_xpath(
                #         "//*[@class='btn btn-primary' and contains(text(), 'Download')]")
                #     elem.click()
                # except WebDriverException:
                #     pass



                c = 0
                while True:

                    try:
                        elem = self.driver.find_element_by_xpath(
                            "//*[@class='btn btn-primary' and contains(text(), 'Download')]")
                        elem.click()
                    except NoSuchElementException:
                        if c >= 9:
                            raise
                        time.sleep(1)
                        c += 1
                        continue
                    break

                # wait until file has downloaded to close the browser. We can do this
                # because we delete the file before we return it, so the temp dir should
                # always be empty when this command is run
                # TODO add a try/except block here
                wait_for_any_file_in_folder(csv_download_folder_path, 'csv')

                report_df = pd.read_csv(get_most_recent_file_in_dir(csv_download_folder_path))

                # delete any files in the mealtime temp folder; we don't need them now
                # TODO: move this out of this function. It should happen as cleanup once
                # the whole DAG has completed
                delete_folder_contents(csv_download_folder_path)

                self.driver.close()
            except WebDriverException:
                if count >= 9:
                    raise
                count += 1
                self.driver.close()
                continue
            break

        return report_df
