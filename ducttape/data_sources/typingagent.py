from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import requests
import pandas as pd
import io
import time
import logging
from random import randint

# local import
from ducttape.webui_datasource import WebUIDataSource
from ducttape.utils import configure_selenium_chrome


class TypingAgent(WebUIDataSource):
    """ Class for interacting with the Typing Agent web ui
    """

    def __init__(self, username, password, wait_time, hostname, temp_folder_path):
        super().__init__(username, password, wait_time, hostname, temp_folder_path)
        self.uri_scheme = 'https://'
        self.base_url = self.uri_scheme + self.hostname
        self.logger = logging.getLogger('sps-automation.data_sources.typingagent.TypingAgent')
        self.logger.debug('creating instance of TypingAgent')

    def _login(self):
        """ Logs into the provided TypingAgent instance.
        """
        self.driver.get(self.base_url)
        # wait until login form available
        try:
            elem = WebDriverWait(self.driver, self.wait_time).until(EC.presence_of_element_located((By.ID, 'LoginForm_username')))
        except TimeoutException:
            raise
        elem.clear()
        elem.send_keys(self.username)
        elem = self.driver.find_element_by_id("LoginForm_password")
        elem.send_keys(self.password)
        elem.send_keys(Keys.RETURN)

    def download_proficiency_report(self, awpm=0, wpm=0, accuracy=0, qscore=0):
        """Downloads the built-in Proficiency Report from Typing Agent.
        
        Args:
            awpm (int): A threshold for the Average Words Per Minute metric. Setting this
                to a value other than the default(0) will filter the report to not include
                students with a value below this threshold.
            wpm (int): A threshold for the Words Per Minute metric. Setting this
                to a value other than the default(0) will filter the report to not include
                students with a value below this threshold.
            accuracy (float): A threshold for the Accuracy metric. Setting this
                to a value other than the default(0) will filter the report to not include
                students with a value below this threshold. This number should be the
                 decimal representation of a percentage (a float between 0 and 1.0).
            qscore (int): A threshold for the Q-Score or "Quality Score" metric. Setting this
                to a value other than the default(0) will filter the report to not include
                students with a value below this threshold.
        
        Returns: A Pandas Dataframe of the Typing Agent Proficiency Report for all of the
            students in all of the grades accessible to this instance of the TypingAgent
            object (all schools and grades that are accessible at the hostname provided
            when this object was instantiated).
        """
        self.logger.info('Beginning download_proficiency_report')
        # input validation
        if awpm < 0 or wpm < 0 or accuracy < 0 or accuracy > 1 or qscore < 0:
            raise ValueError('Inputs to TypingAgent.downlaod_proficiency_report() outside acceptible bounds.')

        # set up the driver for execution
        self.driver = configure_selenium_chrome()
        self._login()

        # get the report url
        self.driver.get("https://app.typingagent.com/index.php?r=district/home/index#/index.php?r=district/report/proficiency")

        # get all of the school codes and names
        try:
            elem_select_school = WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located((By.ID, 'school_prof')))
        except TimeoutException:
            raise

        school_code_options = elem_select_school.find_elements_by_xpath("//*[@id='school_prof']/option")
        schools = list()
        for school_code_option in school_code_options:
            if school_code_option.get_attribute("value") is not "":
                schools.append({
                    'name': school_code_option.text,
                    'code': school_code_option.get_attribute("value")
                })

        # get all of the school grades
        elem_select_grade = self.driver.find_element_by_id('grade_prof')
        grade_options = elem_select_grade.find_elements_by_xpath("//*[@id='grade_prof']/option")
        grades = list()
        for grade_option in grade_options:
            if grade_option.get_attribute("value") is not "":
                grades.append({
                    'name': grade_option.text,
                    'code': grade_option.get_attribute("value")
                })
        # grades = [x.get_attribute("value") for x in grade_options if x.get_attribute("value") is not ""]

        # create requests session to efficiently download multiple files
        with requests.Session() as s:
            for cookie in self.driver.get_cookies():
                s.cookies.set(cookie['name'], cookie['value'])

            dfs_school_grade = list()
            for school in schools:
                for grade in grades:
                    self.logger.info(
                        'Downloading proficiency_report for school, grade: {}, {}'.format(
                            school['name'], grade['name']
                        )
                    )
                    # create GET url
                    report_url = (
                        "https://app.typingagent.com/index.php?r=district/report/ProficiencyReport&"
                        "prof_awpm={}"
                        "&prof_wpm={}"
                        "&prof_accuracy={}"
                        "&prof_qscore={}"
                        "&school_prof={}"
                        "&grade_prof={}"
                        "&export=1"
                    ).format(awpm, wpm, str(int(accuracy*100)), qscore, school['code'], grade['code'])

                    c = 0
                    while True:
                        download_response = s.get(report_url, stream=True)

                        if download_response.ok:
                            df_school_grade = pd.read_csv(io.StringIO(download_response.content.decode('utf-8')))
                            df_school_grade['School Name'] = school['name']
                            df_school_grade['Grade'] = grade['name']

                            dfs_school_grade.append(df_school_grade)
                        else:
                            self.logger.info('Download failed for school, grade: {}, {}'.format(
                                school['name'], grade['name']))
                            self.logger.info('Report URL: {}'.format(report_url))
                            self.logger.info('Download status_code: {}'.format(download_response.status_code))
                            self.logger.info('Retrying... Retry#: {}'.format(c + 1))
                            if c >= 9:
                                raise ValueError('Unable to download report after multiple retries.')
                            # add some jitter to the requests
                            sleep_time = (1000 + randint(500)) / 1000
                            time.sleep(sleep_time)
                            c += 1
                            continue
                        break

        self.driver.close()

        self.logger.info('Proficiency report download complete!')

        return pd.concat(dfs_school_grade, ignore_index=True)

    def download_custom_report(self, custom_report_name):
        """ Downloads a named custom report from Typing Agent
        :param custom_report_name: A string representing the custom report you wish to
                                    download.
        :return: A pandas dataframe with the data from the custom report.
        """
        self.logger.info('Beginning custom_report download for report: {}'.format(
            custom_report_name
        ))
        # set up the driver for execution
        self.driver = configure_selenium_chrome()
        self._login()

        # get the report url
        self.driver.get("https://app.typingagent.com/index.php?r=district/report/index")

        # get list of reports, find one that matches the custom_report_name
        try:
            elem_select_report = Select(WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located((By.ID, 'report_list'))))
        except TimeoutException:
            raise

        # find the that we need to pass in order to download the intended report
        report_options = elem_select_report.options
        for report_option in report_options:
            if report_option.text == custom_report_name:
                custom_report_query_string = report_option.get_attribute("value")
                break

        if not custom_report_query_string:
            raise ValueError('Typing Agent Custom Report not found with name: {}'.format(custom_report_query_string))

        # create requests session to download report without need for file storage
        with requests.Session() as s:
            for cookie in self.driver.get_cookies():
                s.cookies.set(cookie['name'], cookie['value'])

            report_url = self.base_url + custom_report_query_string + '&export=1'

            # download with 10 retries on failure
            c = 0
            while True:
                download_response = s.get(report_url, stream=True)

                if download_response.ok:
                    df_report = pd.read_csv(io.StringIO(download_response.content.decode('utf-8')))
                else:
                    self.logger.info('Download failed for {}'.format(report_option.text))
                    self.logger.info('Report URL: {}'.format(report_url))
                    self.logger.info('Download status_code: {}'.format(download_response.status_code))
                    self.logger.info('Retrying... Retry#: {}'.format(c+1))
                    if c >= 9:
                        raise ValueError('Unable to download report after multiple retries.')
                    # add some jitter to the requests
                    sleep_time = (1000 + randint(500)) / 1000
                    time.sleep(sleep_time)
                    c += 1
                    continue
                break
        self.driver.close()

        self.logger.info('Custom report download complete!')

        return df_report

    def download_url_report(self):
        pass
