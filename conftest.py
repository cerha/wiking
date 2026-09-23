# -*- coding: utf-8 -*-
"""Command line options of the test suite (see 'wiking.test')."""


def pytest_addoption(parser):
    parser.addoption('--language', metavar='LANGUAGE',
                     help="try to use given LANGUAGE in the tested application")
    parser.addoption('--user', metavar='USER[:USER...]',
                     help="use given USER(s) in login forms")
    parser.addoption('--password', metavar='PASSWORD[:PASSWORD...]',
                     help="use given PASSWORD(s) in login forms")
    parser.addoption('--profile', metavar='PROFILE',
                     help="use given web browser PROFILE (see 'wiking.test.BrowserTest')")
