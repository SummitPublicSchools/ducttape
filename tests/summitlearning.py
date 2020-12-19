import pandas as pd
import unittest
import configparser
import ducttape.data_sources.summitlearning as sl
from ducttape.utils import DriverBuilder
from selenium.common.exceptions import NoSuchElementException

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
            'headless': CONFIG.getboolean(config_section_name, 'headless'),
            #'temp_folder_path': CONFIG[config_section_name]['temp_folder_path'],
        }

        cls.sl = sl.SummitLearning(**args)

    def setUp(self):
        self.assertTrue(isinstance(self.sl, sl.SummitLearning))
        #self.addCleanup(self.sl.driver.quit)
        self.addCleanup(self.screen_shot)

    def screen_shot(self):
        for method, error in self._outcome.errors:
            if error:
                self.sl.driver.get_screenshot_as_file("screenshot" + self.id() + ".png")
                with open('page_source_' + self.id() + '.html', 'w') as f:
                    f.write(self.sl.driver.page_source)
        self.sl.driver.quit()

    # @unittest.skip('running subset of tests')
    def test_login(self):
        self.sl.driver = DriverBuilder().get_driver(headless=CONFIG.getboolean('SummitLearning', 'headless'))
        self.sl._login()
        self.sl.driver.close()

    # @unittest.skip('running subset of tests')
    def test_set_dl_academic_year(self):
        year = CONFIG['SummitLearning']['test_set_dl_academic_year__academic_year']
        self.sl.driver = DriverBuilder().get_driver(headless=CONFIG.getboolean('SummitLearning', 'headless'))
        self.sl._login()

        dl_page_url = "{base_url}/sites/{site_id}/data_downloads/".format(
            base_url=self.sl.base_url,
            site_id=CONFIG['SummitLearning']['site_id']
        )

        self.sl.driver.get(dl_page_url)

        result = self.sl._set_dl_academic_year(academic_year=year)

        self.assertTrue(result)

        self.assertTrue(self.sl.check_dl_academic_year(academic_year=year))

    # @unittest.skip('running subset of tests')
    def test_set_dl_academic_year_invalid_year(self):
        year = CONFIG['SummitLearning']['test_set_dl_academic_year_invalid_year__academic_year']
        self.sl.driver = DriverBuilder().get_driver(headless=CONFIG.getboolean('SummitLearning', 'headless'))
        self.sl._login()

        dl_page_url = "{base_url}/sites/{site_id}/data_downloads/".format(
            base_url=self.sl.base_url,
            site_id=CONFIG['SummitLearning']['site_id']
        )

        self.sl.driver.get(dl_page_url)

        self.assertRaises(NoSuchElementException, self.sl._set_dl_academic_year, year)

    # @unittest.skip('running subset of tests')
    def test_download_site_data_download(self):
        heading = "Grades for Currently Enrolled Students (By Student/Course)"

        result = self.sl.download_site_data_download(
            dl_heading=heading,
            site_id=CONFIG['SummitLearning']['site_id'],
            academic_year=CONFIG['SummitLearning']['downloads_academic_year'],
        )

        self.assertTrue(isinstance(result, pd.DataFrame))

        print(result.head())

    # def test_download_url_report_staff_usage(self):
    #     url = CONFIG['SummitLearning']['download_url_report_url']
    #
    #     result = self.sl.download_url_report(url)
    #
    #     self.assertTrue(isinstance(result, pd.DataFrame))
    #
    #     print(result.head())


if __name__ == '__main__':
    summitlearning = unittest.defaultTestLoader.loadTestsFromTestCase(TestSummitLearningDataSource)
    unittest.TextTestRunner().run(summitlearning)