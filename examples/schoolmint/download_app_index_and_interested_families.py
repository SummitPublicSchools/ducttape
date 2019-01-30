###########################################################################################
# download_app_index_and_interested_families.py
# Author: Patrick Yoho (@mryoho on GitHub)
# Date: 2019-01-16
# Description: A sample script that utilises the SchoolMint class from ducttape to
# download the SchoolMint Application Index and Interested Families report. The purpose
# is to demonstrate how to use the SchoolMint object and it is not intended to be
# an exemplar for writing Pythonic code. To make this work in your context, update the
# hostname, username, password, and report_urls.
###########################################################################################
import pandas as pd
from ducttape.data_sources.schoolmint import SchoolMint
from tempfile import mkdtemp
import shutil


def main():
    # The original intention of our automation work was to immediately make data downloaded from
    # different data sources like SchoolMint immediately usable in Pandas, hence most functions
    # return Pandas DataFrames with the downloaded data in them. Since we need to use Selenium to
    # interact with Selenium because of how JavaScript-heavy it is, we do still need to actually
    # download the file, which is easiest to do if you provide the Selenium web driver with some
    # sort of directory to download into. This is defined in the 'temp_folder_path' parameter that
    # is passed to the SchoolMint object constructor below. Again, since that download location is only
    # supposed to be temporary and most data is automatically deleted afterwards, we can use
    # a true temporary directory here using mkdtemp rather than creating our own temporary directory.
    # Hence the following code.
    temp_dir = mkdtemp()

    # create the SchoolMint object for downloading different reports
    schoolmint = SchoolMint(
        # replacing the following with your own creds
        hostname='summit.schoolmint.net',
        username='user@summitps.org',
        password='securepassword',
        wait_time=30,
        temp_folder_path=temp_dir
    )

    # You get the report_url here by going to the report you want to download in SchoolMint and
    # clicking 'Search' to populate the report. You can then just copy and paste the resulting URL
    # as the argument as shown here. The 'download_url_report' works for pretty much everything except
    # for the 'Custom Reports' section, for which there are other functions.
    df_application_index = schoolmint.download_url_report(
        report_url="report/applicants?group=all&school=all&application_status=all&priority=all&district=all&grade=all",
        school_year='2019-2020',
    )

    # Save the data somewhere. Note here that 'df' stands for DataFrame. At Summit, we are in the practice
    # of prepending variables that point to dataframes with 'df' for clarity. The to_csv is a Pandas
    # function.
    df_application_index.to_csv('./application_index.csv')

    # Do similar to download the Interested Families report
    df_interested_familes = schoolmint.download_url_report(
        report_url="report/interestTracker?school=all&grade=all&account_status=all&organization_event_id=all",
        school_year='2019-2020'
    )

    df_interested_familes.to_csv('./interested_families_report.csv')

    # clean up (delete it and its contents) the temporary file that we created at the beginning
    shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()
