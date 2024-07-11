import pandas as pd
import unittest
import time
import configparser
import logging
import sys

from ducttape.data_sources import panorama as panorama
from ducttape.exceptions import (
    InvalidLoginCredentials,
    ReportNotFound,
    InvalidIMAPParameters,
)
from ducttape.utils import configure_selenium_chrome
from oauth2client.service_account import ServiceAccountCredentials
import datetime as dt

logger = logging.getLogger()
logger.level = logging.INFO
stream_handler = logging.StreamHandler(sys.stdout)
logger.addHandler(stream_handler)

config = configparser.ConfigParser()
config.read('./config/config.ini')

class TestSchoolMintDataSource(unittest.TestCase):
    """Test the SchoolMint Object
    """

    @classmethod
    def setUpClass(cls):
        config_section_name = 'Panorama'
        args = {
            'username': config[config_section_name]['username'],
            'password': config[config_section_name]['password'],
            'wait_time': int(config[config_section_name]['wait_time']),
            'temp_folder_path': config[config_section_name]['temp_folder_path'],
            'headless': config[config_section_name].getboolean('headless'),
            'district_suffix': config[config_section_name]['district_suffix']
        }

        cls.pn = panorama.Panorama(**args)

    def setUp(self):
        self.assertTrue(isinstance(self.pn, panorama.Panorama))

    # @unittest.skip('running subset of tests')
    def test_login(self):
        self.pn.driver = configure_selenium_chrome(download_folder_path=self.pn.temp_folder_path)
        try:
            self.pn._login()
        except:
            self.fail("login failed")

    # @unittest.skip('running subset of tests')
    def test_download_admin_report(self):
        report_id = config['Panorama']['report_id']
        self.pn.driver = configure_selenium_chrome(download_folder_path=self.pn.temp_folder_path)
        self.pn._login()
        # Download report and assert that a dataframe was created
        df = self.pn.download_panorama_report_file(report_id)
        self.assertIsNotNone(df)