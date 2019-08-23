# from __future__ import unicode_literals
# from __future__ import print_function
# from __future__ import division
# from __future__ import absolute_import
# from future import standard_library
# standard_library.install_aliases()
from future.utils import with_metaclass
from abc import ABCMeta, abstractmethod, abstractproperty


class WebUIDataSource(with_metaclass(ABCMeta)):
    """Abstract class for data sources that require web UI input.
    """

    def __init__(self, username, password, wait_time, hostname=None,
                 temp_folder_path=None, headless=False):
        self.username = username
        self.password = password
        self.wait_time = wait_time
        if hostname:
            self.hostname = hostname
        if temp_folder_path:
            self.temp_folder_path = temp_folder_path
        self.headless = headless
        self.driver = None

    @abstractmethod
    def _login(self):
        pass

    @abstractmethod
    def download_url_report(self, report_url, temp_folder_name):
        pass


class ExportedDataframe(with_metaclass(ABCMeta)):
    """Abstract class for the data downloaded from a service.
    """

    def __init__(self, filepath):
        self._download_filepath = filepath

    @property
    def download_filepath(self):
        pass

    @abstractproperty
    def filename(self):
        pass

    @abstractproperty
    def shortname(self):
        pass

    @abstractproperty
    def timestamp(self):
        pass

    @abstractproperty
    def dataframe(self):
        pass


