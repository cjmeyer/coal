# test_util.py

import os
import coal
import shutil
import unittest2 as unittest

from coal import error, util
from coal.util import checksignature


def path(p):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), p))


class UtilMkDirTest(unittest.TestCase):
    def tearDown(self):
        if os.path.exists(path("results")):
            shutil.rmtree(path("results"), ignore_errors=True)

    def test_mkdir_new(self):
        util.mkdir(path("results"))
        self.assertTrue(os.path.isdir(path("results")))

    def test_mkdir_parents(self):
        util.mkdir(path("results/path/to/dir"))
        self.assertTrue(os.path.isdir(path("results/path/to/dir")))


class UtilCheckSignatureTest(unittest.TestCase):
    def test_checksignature(self):
        def fn1(a, b, c=None):
            pass

        def fn2(a):
            pass

        self.assertRaises(error.SignatureError, checksignature, (fn1))
        self.assertRaises(error.SignatureError, checksignature, (fn1, 1))
        self.assertRaises(error.SignatureError, checksignature, (fn1, 1, 2, 3, 4))

        self.assertRaises(error.SignatureError, checksignature, (fn2))
        self.assertRaises(error.SignatureError, checksignature, (fn2, 1, 2))

        checksignature(fn1, 1, 2)
        checksignature(fn1, 1, 2, 3)

        checksignature(fn2, 1)


class UtilWrapTest(unittest.TestCase):
    def test_wrap_width(self):
        self.assertEqual(util.wrap("this is a string", 6), "this\nis a\nstring")

    def test_wrap_width_indent(self):
        self.assertEqual(util.wrap("this is a string", 10, "  "), "  this is\na string")

    def test_wrap_width_hanging(self):
        self.assertEqual(util.wrap("this is a string", 8, "", "  "), "this is\n  a\n  string")

    def test_wrap_width_indent_hanging(self):
        self.assertEqual(util.wrap("this is a string", 8, "  ", "  "), "  this\n  is a\n  string")


class UtilColorizeTest(unittest.TestCase):
    def test_colorize_plain_black(self):
        self.assertEqual(util.colorize("Hello", "black"), "\033[30mHello\033[0m")

    def test_colorize_plain_red(self):
        self.assertEqual(util.colorize("Hello", "red"), "\033[31mHello\033[0m")

    def test_colorize_plain_green(self):
        self.assertEqual(util.colorize("Hello", "green"), "\033[32mHello\033[0m")

    def test_colorize_plain_yellow(self):
        self.assertEqual(util.colorize("Hello", "yellow"), "\033[33mHello\033[0m")

    def test_colorize_plain_blue(self):
        self.assertEqual(util.colorize("Hello", "blue"), "\033[34mHello\033[0m")

    def test_colorize_plain_magenta(self):
        self.assertEqual(util.colorize("Hello", "magenta"), "\033[35mHello\033[0m")

    def test_colorize_plain_cyan(self):
        self.assertEqual(util.colorize("Hello", "cyan"), "\033[36mHello\033[0m")

    def test_colorize_plain_white(self):
        self.assertEqual(util.colorize("Hello", "white"), "\033[37mHello\033[0m")

    def test_colorize_bold_red(self):
        self.assertEqual(util.colorize("Hello", "*red*"), "\033[1m\033[31mHello\033[0m")

    def test_colorize_italic_green(self):
        self.assertEqual(util.colorize("Hello", "/green/"), "\033[3m\033[32mHello\033[0m")

    def test_colorize_underline_yellow(self):
        self.assertEqual(util.colorize("Hello", "_yellow_"), "\033[4m\033[33mHello\033[0m")

    def test_colorize_strike_blue(self):
        self.assertEqual(util.colorize("Hello", "-blue-"), "\033[9m\033[34mHello\033[0m")


class UtilClassAccumulateList(unittest.TestCase):
    class Class0(object):
        param = [0]

    class Class1(object):
        param = [1]

    class Class2(Class0, Class1):
        param = []

    class Class3(Class2):
        param = [3]

    def test_accumulate_class_list(self):
        self.assertEqual(sorted(util.accumulate_class_list(self.Class3, 'param')),
                         [0, 1, 3])

