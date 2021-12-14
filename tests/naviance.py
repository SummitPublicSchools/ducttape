import json

import pandas as pd
import unittest
import configparser
import ducttape.data_sources.naviance as nav
import selenium
from ducttape.utils import DriverBuilder
from selenium.common.exceptions import NoSuchElementException

CONFIG = configparser.ConfigParser()
CONFIG.read('./config/config.ini')œ


class TestNavianceDataSource(unittest.TestCase):
    """Test the Naviance Object
    """

    @classmethod
    def setUpClass(cls):
        config_section_name = 'Naviance'
        args = {
            'username': CONFIG[config_section_name]['username'],
            'password': CONFIG[config_section_name]['password'],
            'wait_time': int(CONFIG[config_section_name]['wait_time']),
            'profile_id': int(CONFIG[config_section_name]['profile_id']),
            'headless': CONFIG.getboolean(config_section_name, 'headless'),
            #'temp_folder_path': CONFIG[config_section_name]['temp_folder_path'],
        }

        cls.n = nav.Naviance(**args)

    def setUp(self):
        self.assertTrue(isinstance(self.n, nav.Naviance))
        #self.addCleanup(self.sl.driver.quit)

    def tearDown(self) -> None:
        if self.n.driver is not None:
            self.screen_shot(self.n)

    def screen_shot(self, webuidatasource_object):
        """

        :param webuidatasource_object: A reference to to a subclass of WebUIDataSource
        :return:
        """
        for method, error in self._outcome.errors:
            if error:
                webuidatasource_object.driver.get_screenshot_as_file("screenshot" + self.id() + ".png")
                with open('page_source_' + self.id() + '.html', 'w') as f:
                    f.write(webuidatasource_object.driver.page_source)
        webuidatasource_object.driver.quit()

    @unittest.skip('running subset of tests')
    def test_login(self):
        self.n.driver = DriverBuilder().get_driver(headless=CONFIG.getboolean('Naviance', 'headless'))
        self.n._login()
        self.n.driver.close()

    # # @unittest.skip('running subset of tests')
    # def test_set_dl_academic_year(self):
    #     year = CONFIG['SummitLearning']['test_set_dl_academic_year__academic_year']
    #     self.sl.driver = DriverBuilder().get_driver(headless=CONFIG.getboolean('SummitLearning', 'headless'))
    #     self.sl._login()
    #
    #     dl_page_url = "{base_url}/sites/{site_id}/data_downloads/".format(
    #         base_url=self.sl.base_url,
    #         site_id=CONFIG['SummitLearning']['site_id']
    #     )
    #
    #     self.sl.driver.get(dl_page_url)
    #
    #     result = self.sl._set_dl_academic_year(academic_year=year)
    #
    #     self.assertTrue(result)
    #
    #     self.assertTrue(self.sl.check_dl_academic_year(academic_year=year))
    #
    # # @unittest.skip('running subset of tests')
    # def test_set_dl_academic_year_invalid_year(self):
    #     year = CONFIG['SummitLearning']['test_set_dl_academic_year_invalid_year__academic_year']
    #     self.sl.driver = DriverBuilder().get_driver(headless=CONFIG.getboolean('SummitLearning', 'headless'))
    #     self.sl._login()
    #
    #     dl_page_url = "{base_url}/sites/{site_id}/data_downloads/".format(
    #         base_url=self.sl.base_url,
    #         site_id=CONFIG['SummitLearning']['site_id']
    #     )
    #
    #     self.sl.driver.get(dl_page_url)
    #
    #     self.assertRaises(NoSuchElementException, self.sl._set_dl_academic_year, year)
    #
    # # @unittest.skip('running subset of tests')
    # def test_download_site_data_download_new_interface(self):
    #     heading = "Grades for Currently Enrolled Students (By Student/Course)"
    #
    #     result = self.sl.download_site_data_download(
    #         dl_heading=heading,
    #         site_id=CONFIG['SummitLearning']['site_id'],
    #         academic_year=CONFIG['SummitLearning']['downloads_academic_year'],
    #     )
    #
    #     self.assertTrue(isinstance(result, pd.DataFrame))
    #
    #     print(result.head())
    #
    # # @unittest.skip('running subset of tests')
    # def test_download_site_data_download_old_interface(self):
    #     heading = "Grades for Currently Enrolled Students (By Student/Course)"
    #
    #     result = self.sl_dlcsv.download_site_data_download(
    #         dl_heading=heading,
    #         site_id=CONFIG['SummitLearning_downloadcsv_interface']['site_id'],
    #         academic_year=CONFIG['SummitLearning_downloadcsv_interface']['downloads_academic_year'],
    #     )
    #
    #     self.assertTrue(isinstance(result, pd.DataFrame))
    #
    #     print(result.head())

    @unittest.skip('running subset of tests')
    def test_download_url_report_student_outcomes(self):
        url = CONFIG['Naviance']['download_url_report_url_student_outcomes']

        result = self.n.download_url_report(url)

        self.assertTrue(isinstance(result, pd.DataFrame))

        print(result.head())

    @unittest.skip('running subset of tests')
    def test_download_url_report_student_outcomes_customizations(self):
        url = CONFIG['Naviance']['download_url_report_url_student_outcomes']

        result_no_customization = self.n.download_url_report(url)

        customizations_params = json.loads(CONFIG['Naviance']['download_url_report_url_student_outcomes_json'])

        assert customizations_params is not None
        print(customizations_params)

        result = self.n.download_url_report(url, customization_params=customizations_params)

        self.assertTrue(isinstance(result, pd.DataFrame))
        self.assertFalse(result.equals(result_no_customization))

        print(result.head())

    @unittest.skip('running subset of tests')
    def test_download_student_outcomes_report(self):

        naviance_test_to_check = 'Total Students - Total Students'

        df_result_no_customization = self.n.download_student_outcomes_report()
        self.assertTrue(isinstance(df_result_no_customization, pd.DataFrame))
        # print(df_result_no_customization.head())
        print(df_result_no_customization[df_result_no_customization['Test'] == naviance_test_to_check])

        df_result = self.n.download_student_outcomes_report(start_class_year_grade=2022,
                                                         end_class_year_grade=2034)
        self.assertTrue(isinstance(df_result, pd.DataFrame))
        print(df_result[df_result['Test'] == naviance_test_to_check])

        self.assertFalse(df_result.equals(df_result_no_customization))

    # def test_download_url_report_data_export_student_data(self):
    #     df_result = self.n.download_url_report("")

    def test_download_student_data_export_by_encoded_params(self):
        df_result = self.n.download_data_export_by_encoded_params("exportData=Export+Data&start_year=1900&end_year=2034&district_schools%5B%5D=182120USPU&district_schools%5B%5D=217201USPU&district_schools%5B%5D=180578USPU&district_schools%5B%5D=217025USPU&district_schools%5B%5D=179152USPU&type=0&highschool=182120USPU")

        print(df_result)


if __name__ == '__main__':
    naviance = unittest.defaultTestLoader.loadTestsFromTestCase(TestNavianceDataSource)
    unittest.TextTestRunner().run(naviance)
