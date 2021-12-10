from datetime import datetime
import unittest
import configparser
from ducttape.data_sources import seesaw
from ducttape.utils import DriverBuilder, configure_selenium_chrome
from selenium.common.exceptions import (
    TimeoutException,
    ElementNotVisibleException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

CONFIG = configparser.ConfigParser()
CONFIG.read('./config/config.ini')

class TestSeesawDataSource(unittest.TestCase):
    """Test the Seesaw Object
    """

    @classmethod
    def setUpClass(cls):
        config_section_name = 'Seesaw'
        args = {
            'hostname': CONFIG[config_section_name]['hostname'],
            'username': CONFIG[config_section_name]['username'],
            'password': CONFIG[config_section_name]['password'],
            'wait_time': int(CONFIG[config_section_name]['wait_time']),
            'headless': CONFIG.getboolean(config_section_name, 'headless'),
        }

        cls.ss = seesaw.Seesaw(**args)

    def setUp(self):
        self.assertTrue(isinstance(self.ss, seesaw.Seesaw))
        #self.assertTrue(isinstance(self.ss_dlcsv, ss.Seesaw))
        #self.addCleanup(self.sl.driver.quit)

    def tearDown(self) -> None:
        if self.ss.driver is not None:
            self.screen_shot(self.ss)
        # else:
        #     self.screen_shot(self.sl_dlcsv)

    def screen_shot(self, sl_object):
        """

        :param sl_object: A reference to either self.sl or self.sl_dlc
        :return:
        """
        for method, error in self._outcome.errors:
            if error:
                sl_object.driver.get_screenshot_as_file("screenshot" + self.id() + ".png")
                with open('page_source_' + self.id() + '.html', 'w') as f:
                    f.write(sl_object.driver.page_source)
        sl_object.driver.quit()

    # @unittest.skip('running subset of tests')
    def test_login(self):
        try:
            self.ss.driver = DriverBuilder().get_driver(headless=CONFIG.getboolean('Seesaw', 'headless'))
            self.ss._login()
            self.ss.driver.close()
        except ElementNotVisibleException:
            self.fail("Could not load login page.")
        except TimeoutException:
            self.fail("Login credentials invalid.")

    # @unittest.skip('running subset of tests')
    def test_click_student_activity_report(self):
        self.ss.driver = DriverBuilder().get_driver(headless=CONFIG.getboolean('Seesaw', 'headless'))
        self.ss._login()

        try:
            self.ss._click_student_activity_report()
            popup_elem = WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located(
                    (By.CLASS_NAME, 'MuiTypography-root')))
            self.assertIsNotNone(popup_elem)
            self.assertEquals(popup_elem.text, "Check Your Email in a Bit")
        except:
            self.fail("Failed to successfully navigate to Student Activity Report")

    # @unittest.skip('running subset of tests')
    def test_get_csv_link(self):
        config_section_name = 'Seesaw'
        self.ss.driver = DriverBuilder().get_driver(headless=CONFIG.getboolean('Seesaw', 'headless'))
        self.ss._login()
        self.ss._click_student_activity_report()
        
        link = self.ss._get_csv_link(
            CONFIG[config_section_name]['email_host'], CONFIG[config_section_name]['email_port'], 
            CONFIG[config_section_name]['email_login'], CONFIG[config_section_name]['email_password']
        )

        self.assertIsNotNone(link)
        self.assertIn(".csv", link, "Link not a csv file")

    # @unittest.skip('running subset of tests')
    def test_fetch_date(self):
        d = datetime(2021, 10, 10)
        date_str = self.ss._fetch_date(d)
        self.assertEquals(date_str, "Sunday, October 10, 2021")


    # @unittest.skip('running subset of tests')
    def test_generate_student_activity_report_and_fetch_csv(self):
        config_section_name = 'Seesaw'
        df = self.ss.generate_student_activity_report_and_fetch_csv(
            CONFIG[config_section_name]['email_host'], CONFIG[config_section_name]['email_port'],
            CONFIG[config_section_name]['email_login'], CONFIG[config_section_name]['email_password']
        )
        self.assertIsNotNone(df)

    # @unittest.skip('running subset of tests')
    def test_fetch_school_link_tab_file(self, school_name, report_name, **kwargs):
        config_section_name = 'Seesaw'
        self.ss.driver = configure_selenium_chrome(download_folder_path=self.ss.temp_folder_path)
        self.ss._login()
        df = self.ss.fetch_school_link_tab_file(school_name, report_name, **kwargs)
        self.assertIsNotNone(df)


if __name__ == '__main__':
    seesaw = unittest.defaultTestLoader.loadTestsFromTestCase(TestSeesawDataSource)
    unittest.TextTestRunner().run(seesaw)

