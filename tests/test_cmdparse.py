# test_cmdparse.py


import coal
import mock
import unittest2 as unittest

from coal import cmdparse


class CmdParseTest(unittest.TestCase):
    def setUp(self):
        self.opt_c = mock.Mock()
        self.opt_e = mock.Mock()

        self.opt_c.short_opt.return_value = "c"
        self.opt_c.long_opt.return_value = "charlie"

        self.opt_e.short_opt.return_value = "e"
        self.opt_e.long_opt.return_value = "echo"
        
        self.opts = [
            ("alpha", "a", False, coal.store_const(True)),
            ("bravo", "b", True, coal.store_const(False)),
            ("charlie", "c", None, coal.store(self.opt_c)),
            ("delta", "d", None, coal.store({"00":1, "01":2, "10":3, "11":4})),
            ("echo", "e", None, self.opt_e),
            ("foxtrot", "f", None, coal.append(int)),
            ("golf", "g", None, coal.append({"a":1, "b":2, "c":3, "d":4}))
        ]

    def tearDown(self):
        pass

    def parse(self, s):
        return cmdparse.parse(self.opts, s.split())

    def test_parse_arguments(self):
        self.assertEqual(self.parse("arg1 arg2")[0], ["arg1", "arg2"])

    def test_parse_defaults(self):
        self.assertEqual(self.parse("")[1],
                         {"alpha":False, "bravo":True, "charlie":None,
                          "delta":None, "echo":None, "foxtrot":None,
                          "golf":None})

    def test_parse_short_flag(self):
        self.assertTrue(self.parse("-a")[1]["alpha"])

    def test_parse_short_flags_grouped(self):
        args, opts = self.parse("-ab")
        self.assertTrue(opts["alpha"])
        self.assertFalse(opts["bravo"])

    def test_parse_short_option(self):
        self.opt_c.return_value = mock.Mock()
        self.assertTrue(self.parse("-c ARG")[1]["charlie"], self.opt_c.return_value)

    def test_parse_short_enumerated(self):
        pass

    def test_parse_short_list(self):
        pass

    def test_parse_short_custom(self):
        pass

