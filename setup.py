import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='duct-tape',
    packages=setuptools.find_packages(),
    # using semver 2.0
    version='0.24.1',
    description='Duct Tape is a Python interface for downloading data, uploading data, and controlling supported Ed-Tech software.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='Patrick Yoho',
    author_email='trickyoho@gmail.com',
    url='https://github.com/SummitPublicSchools/ducttape',
    download_url='',
    keywords=['automation', 'education', 'illuminate', 'selenium', 'etl'],
    licencse='GNU GPLv3',
    classifiers=[
        'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent'
    ],
    install_requires=[
        'psycopg2-binary>=2.7.1',
        'paramiko>=2.1.2',
        'beautifulsoup4>=4.5.1',
        'numpy',
        'selenium>=3.4.3',
        'requests>=2.11.1',
        'oauth2client',
        'pandas>=0.20.3',
        'xlrd>=0.9.0',  # Excel support for Pandas
        'future>=0.15.2',
    ]
)
