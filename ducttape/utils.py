from glob import glob
import os
import shutil
from selenium import webdriver
import time
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import logging
import sys
import zipfile

from selenium.webdriver import Chrome
from selenium.webdriver.chrome import webdriver as chrome_webdriver

LOGGER = logging.getLogger('ducttape.utils')


def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def delete_folder_contents(folder_path):
    """Deletes all files and subfolders in a specific folder.

    Args:
        folder_path: The path to the folder whose contents shall be deleted.
    """
    folder = folder_path
    for the_file in os.listdir(folder):
        file_path = os.path.join(folder, the_file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path): shutil.rmtree(file_path)
        except Exception as e:
            print(e)


def get_most_recent_file_in_dir(folder_path):
    """Returns the most recently changed file in a folder.

    Args:
        folder_path: The path to the folder to search
    Returns:
        A string with the filename of the most recently changed file in the
        folder.
    """
    # * means all if need specific format then *.csv
    list_of_files = glob(folder_path + '/*')
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file


def interpret_report_url(base_url, report_url):
    """ Allows flexibility in how report urls are passed to functions

    Args:
        base_url (string): The url including uri scheme and hostname.
            Example: https://summit.schoolmint.net
        report_url (string): A version of the URI of a report. Can either be
            partial or full (the purpose of this function is to recognize
            and correct for if it is partial or full).

    Returns: A string containing the full URL to report.
    """
    # case: full URI is given
    if report_url[0:len(base_url)] == base_url:
        return report_url
    # case: just the ending part of the path is given (missing leading '/')
    elif report_url[0] == '/':
        return base_url + report_url
    else:
        return base_url + '/' + report_url


def wait_for_any_file_in_folder(folder_path, file_format=None, timeout=60):
    """ Waits until the first file shows up in a folder.
    """
    count = 0
    if not file_format:
        file_found = False
        while count < timeout:
            for root, folders, files in os.walk(folder_path):
                # break 'for' loop if files found
                if files:
                    file_found = True
                    break
            print(files)
            # break 'while' loop if files found
            if file_found:
                break
            time.sleep(1)
    else:
        file_found = False
        while count < timeout:
            for root, folders, files in os.walk(folder_path):
                for f in files:
                    if f.endswith(file_format):
                        file_found = True
                        break
                    else:
                        file_found = False
                # break 'for' loop if files found
                if file_found:
                    print(files)
                    break

            # break 'while' loop if files found
            if file_found:
                break
            time.sleep(1)


def correct_list_dataframe_dimensions(rows, columns):

    rows_modified = rows

    for row in rows_modified:
        while len(row) < len(columns):
            row.append(None)

        while len(row) > len(columns):
            row.pop(-1)

    return rows_modified


def configure_selenium_chrome(download_folder_path=None):
    options = webdriver.ChromeOptions()

    # if platform.system() != 'Windows':
    #     option.add_argument('headless')
    # # running chrome headless won't work on windows until version 62
    # if headless:
    #     option.add_argument('headless')
    options.add_argument("window-size=1600,900")
    # run chrome headlessly so we can run it on a headless server
    # options.add_argument('headless')
    # set options to download to temp_folder_path and to not show popups
    if download_folder_path:
        prefs = {
            "profile.default_content_settings.popups": 0,
            "download.default_directory": os.path.abspath(download_folder_path)
        }
        options.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(chrome_options=options)


class DriverBuilder:
    """A set of function used to instantiate a Chrome Selenium Webdriver"""
    def get_driver(self, download_location=None, headless=False, window_size=(1400, 900),
                   chrome_option_prefs=None):
        """
        Convenience function for creating a chrome driver.
        :param download_location: A path to where files should be downloaded. Can be absolute or relative.
        :param headless: A boolean for whether the chromedriver should run without GUI.
        :param window_size: A tuple of l x w for the browser window
        :param chrome_option_prefs: A dict() of any options for to apply to the driver using
        the chrome options class. See http://chromedriver.chromium.org/capabilities and
        https://chromium.googlesource.com/chromium/src/+/master/chrome/common/pref_names.cc
        :return: A selenium web driver.
        """

        driver = self._get_chrome_driver(download_location, headless, chrome_option_prefs)

        driver.set_window_size(*window_size)

        return driver

    def _get_chrome_driver(self, download_location, headless, chrome_option_prefs):
        chrome_options = chrome_webdriver.Options()
        prefs = {}
        if download_location:
            dl_prefs = {'download.default_directory': os.path.abspath(download_location),
                        'download.prompt_for_download': False,
                        'download.directory_upgrade': True,
                        'safebrowsing.enabled': False,
                        'safebrowsing.disable_download_protection': True}

            prefs.update(dl_prefs)

        if chrome_option_prefs:
            prefs.update(chrome_option_prefs)
        chrome_options.add_experimental_option('prefs', prefs)
        
        # when run from a Docker container
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')

        if headless:
            chrome_options.add_argument("--headless")

        driver = Chrome(options=chrome_options)

        return driver


class LoggingMixin(object):
    """
    Convenience super-class to have a logger configured with the class name
    """
    def __init__(self):
        pass

    @property
    def log(self):
        try:
            return self._log
        except AttributeError:
            try:
                self._log = logging.root.getChild(
                    self.__class__.__module__ + '.' + self.__class__.__name__
                )
                return self._log
            # Airflow might block creating a separate logger, so just don't define one.
            except AttributeError:
                LOGGER.info("Using self.log provided by external LoggingMixin.")


def winapi_path(dos_path, encoding=None):
    """
    Turn a Windows dos_path into an extended-length path
    See https://stackoverflow.com/questions/36219317/pathname-too-long-to-open/36237176
    :param dos_path:
    :param encoding:
    :return:
    """
    path = os.path.abspath(dos_path)

    if path.startswith("\\\\"):
        path = "\\\\?\\UNC\\" + path[2:]
    else:
        path = "\\\\?\\" + path

    return path


class ZipfileLongPaths(zipfile.ZipFile):
    """Modified ZipFile that allows Windows Paths longer than 260 char"""
    def _extract_member(self, member, target_path, pwd):
        if sys.platform == 'win32':
            target_path = winapi_path(target_path)
        return zipfile.ZipFile._extract_member(self, member, target_path, pwd)
