from distutils.core import setup
setup(
    name='ducttape',
    packages=['ducttape', 'ducttape.data_sources'],
    version='0.23',
    description='Duct Tape is a Python interface for downloading data, uploading data, and controlling supported Ed-Tech software.',
    author='Patrick Yoho',
    author_email='trickyoho@gmail.com',
    url='https://github.com/SummitPublicSchools/ducttape',
    download_url='',
    keywords=['automation', 'education', 'illuminate', 'selenium', 'etl'],
    classifiers=[],
    install_requires=[
        'psycopg2>=2.7.1',
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
