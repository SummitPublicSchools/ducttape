from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select

from datetime import datetime, timedelta, date

from ducttape.webui_datasource import WebUIDataSource
from ducttape.utils import (
    wait_for_any_file_in_folder,
    get_most_recent_file_in_dir,
    DriverBuilder,
)

import time
import logging

class SEIS(WebUIDataSource):
    """ Class for interacting with web ui of SEIS
    """

    def __init__(self, username, password, hostname, temp_folder_path, wait_time, headless=False):
        super().__init__(username, password, wait_time, hostname, temp_folder_path, headless)
        self.uri_scheme = 'https://'
        self.base_url = self.uri_scheme + self.hostname

    def _login(self):
        """ Logs into the provided SEIS instance
        """
        
        self.driver.get(self.base_url + '/login')
        try:
            elem = WebDriverWait(self.driver, self.wait_time).until(EC.presence_of_element_located((By.NAME, "username")))
        except TimeoutException:
            # TODO add raise LoginFailure or similar
            raise
        assert "SEIS" in self.driver.title
        elem.clear()
        elem.send_keys(self.username)
        elem = self.driver.find_element(By.NAME, "password")
        elem.clear()
        elem.send_keys(self.password)
        elem.send_keys(Keys.RETURN) 
        
    def download_by_search_id(self, search_id, as_of):
        """ Downloads a saved search from SEIS

        Args:
            search_id (integer): The number identifying the report in SEIS.

        Returns:
            Path to the file downloaded
        """
        
        # Setup
        download_folder_path = self.temp_folder_path
        self.driver = DriverBuilder().get_driver(download_folder_path, self.headless)
        self._login()
        time.sleep(3)
        
        # Go to search page
        search_url = self.base_url + '/search/new-search?searchID=' + str(search_id)
        self.driver.get(search_url)
        time.sleep(2)
        
        page_size_elem = WebDriverWait(self.driver, self.wait_time).until(EC.element_to_be_clickable((By.ID, "pageSize")))
        page_size_select = Select(page_size_elem)
        page_size_select.select_by_value("10000")
        time.sleep(3)
        
        elem = WebDriverWait(self.driver, self.wait_time).until(
            EC.element_to_be_clickable((By.ID, "s2id_searchAction"))
        ).find_element(By.TAG_NAME, 'a')
        elem.click()
        input_box = self.driver.find_element(By.ID, 'select2-drop').find_element(By.TAG_NAME, 'input')

        actions = ActionChains(self.driver)
        actions.send_keys_to_element(input_box, 'Download Data')
        actions.send_keys(Keys.ENTER)
        actions.perform()
        
        go_button = self.driver.find_element(By.ID, 'showPer').find_element(By.TAG_NAME, 'button')
        go_button.click()
        
        wait_for_any_file_in_folder(download_folder_path, 'csv')
        self.driver.close()
        
        file = get_most_recent_file_in_dir(download_folder_path)
        logging.info(f'SEIS file for {as_of} downloaded. Filename: {file}')
        return file
    
    def download_url_report(self, report_url, temp_folder_name):
        """May be implemented in the future, but not implemented currently"""
        raise NotImplementedError