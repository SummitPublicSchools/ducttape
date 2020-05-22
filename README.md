![Logo of the project](https://raw.githubusercontent.com/SummitPublicSchools/ducttape/master/img/duct-tape_480x150.png)

# Duct Tape

Duct Tape is a Python interface for downloading data, uploading data, and controlling supported Ed-Tech software.
It is built on top of Requests and Selenium and is intended to help K-12 school system data and IT teams save
time and use "better" code to automate their work flows.

## Currently Supported Products

The following products are currently supported, some have more functionality that others.
* SchoolMint
* Google Sheets
* Lexia
* Clever
* Informed K12
* Mealtime
* Typing Agent
* Summit Learning

## Installing / Getting started

To use this project, complete the following steps (note: we are currently running out of master and 
have not cut a release yet):

0. Set up a Chrome + Selenium environment on your computer. Instructions [here](https://medium.com/@patrick.yoho11/installing-selenium-and-chromedriver-on-windows-e02202ac2b08).
1. Download or clone the project to your computer.
2. Navigate to the root `ducttape` directory in your command line/terminal (the one with the setup.py file in it). Run `pip install ./`.
3. Check out the SchoolMint example in the [`examples`](https://github.com/SummitPublicSchools/ducttape/tree/master/examples) folder to see how easy it can be to grab your data.

## Documentation

A good number of functions have strong doc strings describing their purpose, parameters, and return types.
For now, this along with a couple of [examples](https://github.com/SummitPublicSchools/ducttape/tree/master/examples) are the primary sources of documentation.

## Features

* Downloading data from ed-tech Web UIs without human interaction
* Uploading data to ed-tech through web UIs without human interaction (coming soon)
* Controlling ed-tech web UIs through Python (limited implementation)

The original development purpose of this project was to automate data extraction from ed-tech
products in Python and return them as Pandas dataframes for analysis. Therefore, the biggest
feature set is around downloading flat files from different ed-tech products that don't provide
API and SQL access at all the data you might need to get to. Some work is in progress around
uploading data and controlling other portions of ed-tech platforms, but it is still in
private development.

## Developing

The vision for this project is to have contributors from across different school systems help build
out a centralized, well-coded, tested library for interacting with ed-tech products that don't provide
adequate customer-facing APIs. This will be most successful if contributors come on board as developers
from different school systems; iron will sharpen iron and we will get better coverage of ed-tech products.

If you are interested in developing (and especially if you are interested in adding in support for a new
product), please reach out to pyoho@summitps.org.

#### Ideas for Future Development

* Add the ability to download data from a new product
* Add a missing feature to a currently supported product.
* Fully automating unit testing

## Unit Tests

Unit tests have been written for much of the functionality within this package. These are run
before any commits are made to master. However, they are context specific (in that you need
to use live instances to do the testing) and are not all fully automated (there are still cases
where a human needs to check that the downloaded data meets expected conditions since it is
being tested off of production systems).

A future area of development would be to figure out how to properly mock interacting with
these ed-tech platforms so that we could fully automate unit testing and have better coverage.

## Contributing

If you'd like to contribute new functionality, please reach out to pyoho@summitps.org. If you have
a bug fix or a code clean-up suggestion, feel free to fork us and submit a pull request.

## Licensing

Please see the license file.
