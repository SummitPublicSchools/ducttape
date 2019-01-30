import pandas as pd
import unittest
import time
import configparser
import logging
import sys

from ducttape.data_sources import schoolmint as sm
from ducttape.data_sources.googlesheets import GoogleSpreadsheet
from ducttape.data_sources import mealtime as mt
from ducttape.data_sources import clever as cl
from ducttape.data_sources import typingagent as ta
from ducttape.data_sources import informedk12 as ik12
from ducttape.data_sources import lexia as lx
from ducttape.exceptions import (
    InvalidLoginCredentials,
    ReportNotFound
)
from oauth2client.service_account import ServiceAccountCredentials
import datetime as dt

# logger = logging.getLogger()
# logger.level = logging.DEBUG
# stream_handler = logging.StreamHandler(sys.stdout)
# logger.addHandler(stream_handler)

config = configparser.ConfigParser()
config.read('./config/config.ini')

SPREADSHEET_ID = config['GoogleSheets']['test_spreadsheet_id']
SCOPE = [
    'https://www.googleapis.com/auth/spreadsheets'
]


class TestLexiaDataSource(unittest.TestCase):
    """Test the Lexia Object
    """

    @classmethod
    def setUpClass(cls):
        config_section_name = 'Lexia'
        args = {
            'hostname': config[config_section_name]['hostname'],
            'username': config[config_section_name]['username'],
            'password': config[config_section_name]['password'],
            'wait_time': int(config[config_section_name]['wait_time']),
            'temp_folder_path': config[config_section_name]['temp_folder_path'],
            'lexia_school_year_start_date': dt.datetime.strptime(
                config[config_section_name]['lexia_school_year_start_date'],
                '%Y-%m-%d'
            ).date(),
            'headless': config[config_section_name].getboolean('headless'),
            'district_export_email_address': config[config_section_name]['district_export_email_address'],
            'district_export_email_password': config[config_section_name]['district_export_email_password'],
            'district_export_email_imap_uri': config[config_section_name]['district_export_email_imap_uri'],
            'district_id': int(config[config_section_name]['district_id'])
        }

        cls.lx = lx.Lexia(**args)

        args_bad_login = {
            'hostname': config[config_section_name]['hostname'],
            'username': config[config_section_name]['username'],
            'password': '',
            'wait_time': int(config[config_section_name]['wait_time']),
            'temp_folder_path': config[config_section_name]['temp_folder_path'],
            'headless': config[config_section_name].getboolean('headless'),
        }

        cls.lx_bad_login = lx.Lexia(**args_bad_login)

    def setUp(self):
        self.assertTrue(isinstance(self.lx, lx.Lexia))

    @unittest.skip('running subset of tests')
    def test_bad_login(self):
        url = (
            "/mylexiaweb/app/index.html#/19048/reading/staff-usage"
        )
        with self.assertRaises(InvalidLoginCredentials):
            self.lx_bad_login.download_url_report(url)

    @unittest.skip('running subset of tests')
    def test_download_url_report_staff_usage(self):
        url = (
            "/mylexiaweb/app/index.html#/19048/reading/staff-usage"
        )

        result = self.lx.download_url_report(url)

        self.assertTrue(isinstance(result, pd.DataFrame))

        print(result.head())

    @unittest.skip('running subset of tests')
    def test_download_url_report_with_manage_tab_address(self):
        url = (
            "/mylexiaweb/app/index.html#/groups/staff"
        )

        result = self.lx.download_url_report(url)

        self.assertTrue(isinstance(result, pd.DataFrame))

        print(result.head())

    @unittest.skip('running subset of tests')
    def test_download_manage_tab_report_staff(self):
        url = (
            "/mylexiaweb/app/index.html#/groups/staff"
        )

        result = self.lx.download_manage_tab_report(url)

        self.assertTrue(isinstance(result, pd.DataFrame))

        # it has the right number of columns
        self.assertTrue(result.shape[1] == 7)

        print(result.head())

    @unittest.skip('running subset of tests')
    def test_download_manage_tab_report_students(self):
        url = (
            "/mylexiaweb/app/index.html#/groups/students"
        )

        result = self.lx.download_manage_tab_report(url)

        self.assertTrue(isinstance(result, pd.DataFrame))

        # it has the right number of columns
        self.assertTrue(result.shape[1] == 14)

        print(result.head())

    @unittest.skip('running subset of tests')
    def test_download_manage_tab_report_students_save(self):
        url = (
            "/mylexiaweb/app/index.html#/groups/students"
        )

        result = self.lx.download_manage_tab_report(
            url,
            write_to_disk='./data/lexia/'
        )

        self.assertTrue(isinstance(result, pd.DataFrame))

        # it has the right number of columns
        self.assertTrue(result.shape[1] == 14)

        # TODO add assertion that file is created in expected dir

    #@unittest.skip('running subset of tests')
    def test_download_district_export_core5_monthly(self):
        self.lx.download_district_export_core5_monthly()

    @unittest.skip('running subset of tests')
    def test_get_exportid_from_email(self):
        self.lx._get_exportid_from_email()


class TestSchoolMintDataSource(unittest.TestCase):
    """Test the SchoolMint Object
    """

    @classmethod
    def setUpClass(cls):
        config_section_name = 'SchoolMint'
        args = {
            'hostname': config[config_section_name]['hostname'],
            'username': config[config_section_name]['username'],
            'password': config[config_section_name]['password'],
            'wait_time': int(config[config_section_name]['wait_time']),
            'temp_folder_path': config[config_section_name]['temp_folder_path'],
            'headless': config[config_section_name].getboolean('headless')
        }

        cls.sm = sm.SchoolMint(**args)

    def setUp(self):
        self.assertTrue(isinstance(self.sm, sm.SchoolMint))

    @unittest.skip('running subset of tests')
    def test_login(self):
        pass

    @unittest.skip('running subset of tests')
    def test_download_url_report(self):
        url = (
            "/report/applicantsDynamicTable?group=all&school=all&application_status=all"
            "&priority=all&district=all&grade=all&include[]=last_first_middle_name"
            "&include[]=school&include[]=grade&include[]=status&include[]=offer_date"
            "&include[]=status_change_on&include[]=accepted_applied"
        )

        result = self.sm.download_url_report(url, '2018-2019')

        self.assertTrue(isinstance(result, pd.DataFrame))

        print(result.head())

    @unittest.skip('running subset of tests')
    def test_generate_custom_report(self):
        custom_report_name = 'Re-enrollment Data'
        # generate the report
        result_one = self.sm.generate_custom_report(custom_report_name, '2018-2019')

        self.assertTrue(result_one)

        # give the schoolmint system some time to register the request and update the interface
        time.sleep(45)

        # try to generate it again. it should fail and return false. it should not raise an exception
        result_two = self.sm.generate_custom_report(custom_report_name, '2018-2019')

        self.assertTrue(not result_two)

    @unittest.skip('running subset of tests')
    def test_generate_custom_report_report_on_different_page(self):
        custom_report_name = 'All form data form Additional 18-19 Enrollment Forms - Rainier'
        result = self.sm.generate_custom_report(custom_report_name, '2018-2019')

        self.assertTrue(result)

    @unittest.skip('running subset of tests')
    def test_get_last_custom_report_generation_time(self):
        custom_report_name = 'Application Data'

        dt = self.sm.get_last_custom_report_generation_datetime(custom_report_name, '2018-2019')

        print(dt)

        # We will need to check the datetime is returned properly manually
        return True

    @unittest.skip('running subset of tests')
    def test_download_csv_custom_report(self):
        custom_report_name = 'All Siblings'
        school_year = '2017-2018'

        result = self.sm.download_csv_custom_report(custom_report_name, school_year)

        self.assertTrue(isinstance(result, pd.DataFrame))

        print(result.head())

    @unittest.skip('running subset of tests')
    def test_set_year(self):
        year = '2016-2017'
        result = self.sm._set_year(year)

        self.assertTrue(result)

    #@unittest.skip('running subset of tests')
    def test_download_csv_custom_report_with_year_change(self):
        custom_report_name = 'Conversion Rates CA'
        school_year = '2015-2016'

        result = self.sm.download_csv_custom_report(custom_report_name, school_year)

        self.assertTrue(isinstance(result, pd.DataFrame))

        print(result.head())

    @unittest.skip('running subset of tests')
    def test_download_zip_custom_report(self):
        custom_report_name = 'Application Data'
        school_year = '2018-2019'

        result = self.sm.download_zip_custom_report(
            report_name=custom_report_name,
            school_year=school_year,
            #download_folder_path='./data/schoolmint/custom_reports',
            download_if_generating=True,
            unzip=True
        )

        self.assertTrue(isinstance(result, dict))

        self.assertTrue(isinstance(result['application_data_exporter'], pd.DataFrame))

        print(result.keys())

        print(result['application_data_exporter'].head())


class TestInformedK12DataSource(unittest.TestCase):
    """Test the Informed K12 Object
    """

    @classmethod
    def setUpClass(cls):
        config_section_name = 'InformedK12'
        args = {
            'hostname': config[config_section_name]['hostname'],
            'username': config[config_section_name]['username'],
            'password': '',
            'wait_time': int(config[config_section_name]['wait_time']),
            'temp_folder_path': config[config_section_name]['temp_folder_path'],
        }

        cls.ik12 = ik12.InformedK12(**args)

    def setUp(self):
        self.assertTrue(isinstance(self.ik12, ik12.InformedK12))

    def test_download_url_report(self):
        report_url = (
            'campaigns/denali-registration-packet-electronic-form-denali-contact-info-2017-18/responses?sort_by='
            'last_activity&direction=desc&page=1&page_size=50&filters=%7B%22status_group%22%3A%22active%22%7D'
        )

        df_result = self.ik12.download_url_report(report_url, 'student_list')

        print(df_result)


class TestTypingAgentDataSource(unittest.TestCase):
    """Test the TypingAgent Object
    """

    @classmethod
    def setUpClass(cls):
        config_section_name = 'TypingAgent'
        args = {
            'hostname': config[config_section_name]['hostname'],
            'username': config[config_section_name]['username'],
            'password': config[config_section_name]['password'],
            'wait_time': int(config[config_section_name]['wait_time']),
            'temp_folder_path': config[config_section_name]['temp_folder_path'],
        }

        cls.ta = ta.TypingAgent(**args)

    def setUp(self):
        self.assertTrue(isinstance(self.ta, ta.TypingAgent))

    #@unittest.skip('running subset of tests')
    def test_download_proficiency_report(self):
        df_filtered = self.ta.download_proficiency_report(awpm=40, wpm=40, accuracy=0.7, qscore=0)
        df_unfiltered = self.ta.download_proficiency_report()

        print('df_filtered shape: {}'.format(df_filtered.shape))
        print('df_unfiltered shape: {}'.format(df_unfiltered.shape))

    def test_download_custom_report(self):
        custom_report_name = 'Custom Proficiency'
        df = self.ta.download_custom_report(custom_report_name)
        print(df.head())
        print(df.shape)


class GoogleSpreadsheetTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        private_key_path = config['GoogleSheets']['oauth_private_key_path']
        credentials = ServiceAccountCredentials.from_json_keyfile_name(private_key_path, SCOPE)
        cls.gs = GoogleSpreadsheet(credentials)

    def setUp(self):
        self.assertTrue(isinstance(self.gs, GoogleSpreadsheet))

    def test_download_worksheet_range(self):
        """
        This tests the following aspects:
        * That a full row is downloaded
        * According to the Google Sheets API V4, the values returned 'For output,
          [will not include] empty trailing rows and columns' This includes trailing columns in row 3.
        * That the replacement of white-space only strings with np.nan happens
        """
        import numpy as np

        worksheet_title = 'Test Download Range'

        header = ['School Name', 'Local Student ID', 'SM Application ID', 'SM Applicant ID', 'SM Account ID',
                  'SM Student ID', 'SM Application Year', 'First Name', 'Middle Name', 'Last Name', 'Birth Date',
                  'Date LSID Assigned',	'LSID Taken?']

        rows = [
            ['Summit Preparatory Charter High School','10100','1234','2345','3456','4567','2017','Billy','Joel','Idol',
             '12/1/1953','12/17/2016','1'],
            ['Summit Preparatory Charter High School','10101',np.nan,np.nan,np.nan,np.nan,np.nan,np.nan,np.nan,np.nan,
             np.nan,np.nan,'0'],
            ['Summit Preparatory Charter High School','10102',np.nan,np.nan,np.nan,np.nan,np.nan,np.nan,np.nan,np.nan,
             np.nan,np.nan,np.nan]
        ]

        df_expected = pd.DataFrame(rows, columns=header)

        range = "'{}'!{}:{}".format(worksheet_title, 'A', 'M')

        df_result = self.gs.download_worksheet_range(SPREADSHEET_ID, range)

        self.assertTrue(df_result.equals(df_expected))

    # @unittest.skip('running subset of tests')
    def test_get_dimensions(self):
        worksheet_title = 'Test Dimensions'

        rows, cols = self.gs.get_worksheet_dimensions(SPREADSHEET_ID, worksheet_title)

        self.assertTrue(rows == 10)
        self.assertTrue(cols == 4)

    def test_get_worksheet_id(self):
        worksheet_title = 'Test Worksheet ID'

        result = self.gs.get_worksheet_id(SPREADSHEET_ID, worksheet_title)

        self.assertTrue(result == 2121625460)

    # @unittest.skip('running subset of tests')
    def test_delete_worksheet_dimension_rows(self):
        worksheet_title = 'Test Dimension Functions'
        num_rows_to_delete = 1

        num_rows_current = self.gs.get_worksheet_dimensions(SPREADSHEET_ID, worksheet_title)[0]

        result = self.gs.delete_worksheet_dimension(SPREADSHEET_ID, worksheet_title, 'rows', 0, num_rows_to_delete)

        self.assertTrue(result)

        num_rows_new = self.gs.get_worksheet_dimensions(SPREADSHEET_ID, worksheet_title)[0]

        self.assertTrue(num_rows_new == num_rows_current - num_rows_to_delete)

    # @unittest.skip('running subset of tests')
    def test_delete_worksheet_dimension_columns(self):
        worksheet_title = 'Test Dimension Functions'
        num_columns_to_delete = 1

        num_columns_current = self.gs.get_worksheet_dimensions(SPREADSHEET_ID, worksheet_title)[1]

        result = self.gs.delete_worksheet_dimension(SPREADSHEET_ID, worksheet_title, 'columns', 0, num_columns_to_delete)

        self.assertTrue(result)

        num_columns_new = self.gs.get_worksheet_dimensions(SPREADSHEET_ID, worksheet_title)[1]

        self.assertTrue(num_columns_new == num_columns_current - num_columns_to_delete)

    def test_delete_rows_from_bottom_of_worksheet(self):
        # TODO: This test really needs to be more robust, it requires a human to check that
        # the correct values are being deleted right now.
        worksheet_title = 'Test Dimension Functions'
        num_rows_to_delete = 2

        num_rows_current = self.gs.get_worksheet_dimensions(SPREADSHEET_ID, worksheet_title)[0]

        result = self.gs.delete_rows_from_bottom_of_worksheet(SPREADSHEET_ID, worksheet_title, num_rows_to_delete)

        num_rows_new = self.gs.get_worksheet_dimensions(SPREADSHEET_ID, worksheet_title)[0]

        self.assertTrue(num_rows_new == num_rows_current - num_rows_to_delete)
        
    def test_delete_columns_from_right_of_worksheet(self):
        # TODO: This test really needs to be more robust, it requires a human to check that
        # the correct values are being deleted right now.
        worksheet_title = 'Test Dimension Functions'
        num_cols_to_delete = 2

        num_cols_current = self.gs.get_worksheet_dimensions(SPREADSHEET_ID, worksheet_title)[1]

        result = self.gs.delete_columns_from_right_of_worksheet(SPREADSHEET_ID, worksheet_title, num_cols_to_delete)

        num_cols_new = self.gs.get_worksheet_dimensions(SPREADSHEET_ID, worksheet_title)[1]

        self.assertTrue(num_cols_new == num_cols_current - num_cols_to_delete)

    def test_append_worksheet_dimension_rows(self):
        worksheet_title = 'Test Dimension Functions'
        num_rows_to_append = 3

        num_rows_current = self.gs.get_worksheet_dimensions(SPREADSHEET_ID, worksheet_title)[0]

        result = self.gs.append_worksheet_dimension(SPREADSHEET_ID, worksheet_title, 'rows', num_rows_to_append)

        self.assertTrue(result)

        num_rows_new = self.gs.get_worksheet_dimensions(SPREADSHEET_ID, worksheet_title)[0]

        self.assertTrue(num_rows_new == num_rows_current + num_rows_to_append)

    def test_append_worksheet_dimension_columns(self):
        worksheet_title = 'Test Dimension Functions'
        num_cols_to_append = 3

        num_cols_current = self.gs.get_worksheet_dimensions(SPREADSHEET_ID, worksheet_title)[1]

        result = self.gs.append_worksheet_dimension(SPREADSHEET_ID, worksheet_title, 'columns', num_cols_to_append)

        self.assertTrue(result)

        num_cols_new = self.gs.get_worksheet_dimensions(SPREADSHEET_ID, worksheet_title)[1]

        self.assertTrue(num_cols_new == num_cols_current + num_cols_to_append)

    def test_set_worksheet_dimensions(self):
        worksheet_title = 'Test Set Worksheet Dimensions'

        # check that the desired dimensions were set correctly
        desired_dimensions = (10, 10)

        result = self.gs.set_worksheet_dimensions(SPREADSHEET_ID, worksheet_title, desired_dimensions[0], desired_dimensions[1])

        resultant_dimensions = self.gs.get_worksheet_dimensions(SPREADSHEET_ID, worksheet_title)

        self.assertTrue(resultant_dimensions[0] == desired_dimensions[0])
        self.assertTrue(resultant_dimensions[1] == desired_dimensions[1])

        # check that data in the upper left corner was preserved
        header = ["Student ID", 'First Name', 'Last Name']

        expected_values = [['123456', 'John', 'Doe']]

        df_expected = pd.DataFrame(expected_values, columns=header)

        df_result = self.gs.download_worksheet_range(SPREADSHEET_ID, "'{}'!{}:{}".format(worksheet_title, "A1", "F2"))

        self.assertTrue(df_result.equals(df_expected))

    # @unittest.skip('running subset of tests')
    def test_clear_worksheet_range(self):
        range_to_clear = 'Test Clear!A1:B10'

        result = self.gs.clear_worksheet_range(SPREADSHEET_ID, range_to_clear)

        self.assertTrue(result)

    def test_update_worksheet_range(self):
        range_to_update = 'Test Clear!A1:B10'

        rows = [
            [1, 1],
            [1, 1],
            [1, 1],
            [1, 1],
            [1, 1],
            [1, 1],
            [1, 1],
            [1, 1],
            [1, 1],
            [1, 1]
        ]

        result = self.gs.update_worksheet_range(SPREADSHEET_ID, range_to_update, rows)

        self.assertTrue(result)

    # @unittest.skip('Weird stuff going on')
    def test_replace_worksheet_with_dataframe(self):
        worksheet_title = 'Test Replace with Dataframe'

        df_header = ['Student ID', 'First Name', 'Last Name', 'Favorite Color']

        df_rows = [
            ['123456', 'John', 'Doe', 'Pink'],
            ['123457', 'Sally', 'Mae', 'Blue']
        ]

        df_expected = pd.DataFrame(df_rows, columns=df_header)

        self.gs.replace_worksheet_with_dataframe(SPREADSHEET_ID, worksheet_title, df_expected, 'B2')

        df_result = self.gs.download_worksheet_range(SPREADSHEET_ID, "'{}'!{}:{}".format(worksheet_title, "B2", "F4"))

        self.assertTrue(df_result.equals(df_expected))

    def test_replace_worksheet_with_dataframe_no_header(self):
        worksheet_title = 'Test Replace with DataFrame - No Header'

        df_header = ['Student ID', 'First Name', 'Last Name', 'Favorite Color']

        df_rows = [
            ['123456', 'John', 'Doe', 'Pink'],
            ['123457', 'Sally', 'Mae', 'Blue']
        ]

        df_upload = pd.DataFrame(df_rows, columns=df_header)

        self.gs.replace_worksheet_with_dataframe(SPREADSHEET_ID, worksheet_title, df_upload, 'B2', False)

        # note - this test case does not yet have an automated way of determining if it worked or not.
        # This will have to be checked visually
        # https://docs.google.com/spreadsheets/d/1skpmwQP2yrUjkVTks9x92-5vRNOV0FbeHQNE9dvq47E/edit#gid=1678038755
        self.assertTrue(False)

    def test_a1_to_rowcol(self):
        a1_notation = 'B2'

        row_expected, col_expected = 1, 1

        row_result, col_result = self.gs._a1_to_rowcol_index(a1_notation)

        self.assertTrue(row_result == row_expected)
        self.assertTrue(col_result == col_expected)


class TestMealtimeDataSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config_section_name = 'Mealtime'
        args = {
            'hostname': config[config_section_name]['hostname'],
            'username': config[config_section_name]['username'],
            'password': config[config_section_name]['password'],
            'wait_time': int(config[config_section_name]['wait_time']),
            'temp_folder_path': config[config_section_name]['temp_folder_path'],
            'headless': config[config_section_name].getboolean('headless')
        }

        cls.mt = mt.Mealtime(**args)

    def setUp(self):
        self.assertTrue(isinstance(self.mt, mt.Mealtime))

    def test_download_url_report(self):
        report_url = (
            'Eligibility/RPTStudentListing.aspx?reportMode=ViewReport&qaReportPath=&qaReportName=&pmi=1078&tmi=714'
            '&showEligibilityAlias=&showActiveOnly=true&singleDateType=Today&singleToDate=07%2F17%2F2017&eligType='
            '&school=&grade=&appSrc=&elig=&allIncomeApps=true&allCategoricalApps=true&allAgencyCerts=true&allMisc=true'
        )

        df_result = self.mt.download_url_report(report_url, 'student_list')

        print(df_result)


class TestCleverDataSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config_section_name = 'Clever'
        args = {
            'hostname': config[config_section_name]['hostname'],
            'username': config[config_section_name]['username'],
            'password': config[config_section_name]['password'],
            'wait_time': int(config[config_section_name]['wait_time']),
            'temp_folder_path': config[config_section_name]['temp_folder_path']
        }

        cls.cl = cl.Clever(**args)

        args_bad_login = {
            'hostname': config[config_section_name]['hostname'],
            'username': config[config_section_name]['username'],
            'password': 'woo!',
            'wait_time': int(config[config_section_name]['wait_time']),
            'temp_folder_path': config[config_section_name]['temp_folder_path']
        }

        cls.cl_bad_login = cl.Clever(**args_bad_login)

    def setUp(self):
        self.assertTrue(isinstance(self.cl, cl.Clever))
        self.assertTrue(isinstance(self.cl_bad_login, cl.Clever))
        self.app_to_test_url = config['Clever']['app_to_test_url']

    # @unittest.skip('running subset of tests')
    def test_bad_login(self):
        with self.assertRaises(InvalidLoginCredentials):
            self.cl_bad_login.download_url_report(
                report_url=self.app_to_test_url,
                collection='students',
            )

    # @unittest.skip('running subset of tests')
    def test_download_url_reports_students(self):
        df_result = self.cl.download_url_report(
            report_url=self.app_to_test_url,
            collection='students',
        )
        self.assertTrue(isinstance(df_result, pd.DataFrame))
        self.assertTrue(df_result.shape[0] > 0)
        print(df_result)

    def test_download_data_shared_with_application_schools(self):
        df_result = self.cl.download_data_shared_with_application(
            application_page_url=self.app_to_test_url,
            collection='schools',
        )
        self.assertTrue(isinstance(df_result, pd.DataFrame))
        self.assertTrue(df_result.shape[0] > 0)
        print(df_result)

    def test_download_data_shared_with_application_sections(self):
        df_result = self.cl.download_data_shared_with_application(
            application_page_url=self.app_to_test_url,
            collection='sections',
        )
        self.assertTrue(isinstance(df_result, pd.DataFrame))
        self.assertTrue(df_result.shape[0] > 0)
        print(df_result)

    def test_download_data_shared_with_application_teachers(self):
        df_result = self.cl.download_data_shared_with_application(
            application_page_url=self.app_to_test_url,
            collection='teachers',
        )
        self.assertTrue(isinstance(df_result, pd.DataFrame))
        self.assertTrue(df_result.shape[0] > 0)
        print(df_result)

    def test_download_data_shared_with_application_schooladmins(self):
        df_result = self.cl.download_data_shared_with_application(
            application_page_url=self.app_to_test_url,
            collection='schooladmins',
        )
        self.assertTrue(isinstance(df_result, pd.DataFrame))
        print(df_result)

    def test_download_data_shared_with_application_bad_collection(self):
        with self.assertRaises(ReportNotFound):
            self.cl.download_data_shared_with_application(
                application_page_url=self.app_to_test_url,
                collection='student',
            )

    @unittest.skip('no longer have credentials to test')
    def test_download_google_accounts_manager_student_export(self):
        df_result = self.cl.download_google_accounts_manager_student_export()

        print(df_result)


if __name__ == '__main__':
    # uncomment the next two lines to just test the SchoolMint code
    # lexia = unittest.defaultTestLoader.loadTestsFromTestCase(TestLexiaDataSource)
    # unittest.TextTestRunner().run(lexia)

    # uncomment the next two lines to just test the SchoolMint code
    schoolmint = unittest.defaultTestLoader.loadTestsFromTestCase(TestSchoolMintDataSource)
    unittest.TextTestRunner().run(schoolmint)

    # uncomment the next two lines to just test the GoogleSpreadsheet code
    # googlesheets = unittest.defaultTestLoader.loadTestsFromTestCase(GoogleSpreadsheetTest)
    # unittest.TextTestRunner().run(googlesheets)

    # uncomment the next two lines to just test the Mealtime code
    # mealtime = unittest.defaultTestLoader.loadTestsFromTestCase(TestMealtimeDataSource)
    # unittest.TextTestRunner().run(mealtime)

    # uncomment the next two lines to just test the Clever code
    # clever = unittest.defaultTestLoader.loadTestsFromTestCase(TestCleverDataSource)
    # unittest.TextTestRunner().run(clever)

    # uncomment the neext two lines to just test the Informed K12 code
    # informedk12 = unittest.defaultTestLoader.loadTestsFromTestCase(TestInformedK12DataSource)
    # unittest.TextTestRunner().run(informedk12)

    # uncomment the next two lines to just test the Typing Agent code
    # typingagent = unittest.defaultTestLoader.loadTestsFromTestCase(TestTypingAgentDataSource)
    # unittest.TextTestRunner().run(typingagent)

    # uncomment the following line to run all tests.
    #unittest.main()
