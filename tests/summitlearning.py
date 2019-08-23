import pandas as pd
import unittest
import configparser
import ducttape.data_sources.summitlearning as sl
from ducttape.utils import DriverBuilder

CONFIG = configparser.ConfigParser()
CONFIG.read('./config/config.ini')


class TestSummitLearningDataSource(unittest.TestCase):
    """Test the SummitLearning Object
    """

    @classmethod
    def setUpClass(cls):
        config_section_name = 'SummitLearning'
        args = {
            'username': CONFIG[config_section_name]['username'],
            'password': CONFIG[config_section_name]['password'],
            'wait_time': int(CONFIG[config_section_name]['wait_time']),
            #'temp_folder_path': CONFIG[config_section_name]['temp_folder_path'],
        }

        cls.sl = sl.SummitLearning(**args)

    def setUp(self):
        self.assertTrue(isinstance(self.sl, sl.SummitLearning))

    def test_login(self):
        self.sl.driver = DriverBuilder().get_driver()
        self.sl._login()
        self.sl.driver.close()

    def test_download_url_report_staff_usage(self):
        url = CONFIG['SummitLearning']['download_url_report_url']

        result = self.sl.download_url_report(url)

        self.assertTrue(isinstance(result, pd.DataFrame))

        print(result.head())


if __name__ == '__main__':
    summitlearning = unittest.defaultTestLoader.loadTestsFromTestCase(TestSummitLearningDataSource)
    unittest.TextTestRunner().run(summitlearning)