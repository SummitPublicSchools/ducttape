import pandas as pd
import unittest
import configparser
from ducttape.data_sources import seesaw as ss
import selenium
from ducttape.utils import DriverBuilder
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementNotVisibleException,
)

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

        cls.ss = ss.Seesaw(**args)
        """
        # set up second class for testing the old 'Download CSV' interface
        config_section_name_downloadcsv = 'Seesaw_downloadcsv_interface'
        args = {
            'username': CONFIG[config_section_name_downloadcsv]['username'],
            'password': CONFIG[config_section_name_downloadcsv]['password'],
            'wait_time': int(CONFIG[config_section_name]['wait_time']),
            'headless': CONFIG.getboolean(config_section_name, 'headless'),
        }

        cls.ss_dlcsv = ss.Seesaw(**args)
        """

    def setUp(self):
        self.assertTrue(isinstance(self.ss, ss.Seesaw))
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

    @unittest.skip('running subset of tests')
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


if __name__ == '__main__':
    seesaw = unittest.defaultTestLoader.loadTestsFromTestCase(TestSeesawDataSource)
    unittest.TextTestRunner().run(seesaw)
