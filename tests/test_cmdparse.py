# test_cmdparse.py


import coal
import mock
import unittest2 as unittest

from coal import cmdparse, error
from coal.cmdparse import opt, store_const, store, append


class CmdParseTest(unittest.TestCase):
    def setUp(self):
        self.opt_c = mock.Mock()
        self.opt_e = mock.Mock()

        self.opt_c.return_value = mock.Mock()
        self.opt_e.return_value = mock.Mock()

        self.command1 = mock.Mock()
        self.command2 = mock.Mock()

        self.cmdtable = {
            "cmd1|command1":
                (self.command1,
                 [opt("a", "alpha", store, int),
                  opt("g", "golf", store_const, True),
                  opt("h", "hotel", append, {"a":1, "b":2, "c":3, "d":4})],
                 "usage string"),
            "cmd2":
                (self.command2,
                 [opt("a", "alpha", store, float),
                  opt("g", "golf", store_const, False),
                  opt("h", "hotel", append, int)],
                 "usage string")
        }

        self.opts = [
            opt("a", "alpha", store_const, True),
            opt("b", "bravo", store_const, False),
            opt("c", "charlie", store, self.opt_c),
            opt("d", "delta", store, {"00":1, "01":2, "10":3, "11":4}),
            opt("e", "echo", append, int),
            opt("f", "foxtrot", append, {"a":1, "b":2, "c":3, "d":4})
        ]

    def tearDown(self):
        pass

    def parse(self, s, cmdtable=None):
        if cmdtable is None:
            cmdtable = self.cmdtable
        return cmdparse.parse(self.opts, cmdtable, s.split())

    def opt_test(self, s, args, opts):
        args_, opts_ = self.parse(s, {})
        self.assertEqual(args_, args)
        self.assertEqual(opts_, opts)

    def cmd_test(self, s, opts, cmd, cmdargs, cmdopts):
        args_, opts_ = self.parse(s, self.cmdtable)
        args_[0]()
        self.assertEqual(opts_, opts)
        cmd.assert_called_once_with(*cmdargs, **cmdopts)

    def test_opt_parse_arguments(self):
        self.opt_test("arg1 arg2", ["arg1", "arg2"], {})

    def test_opt_parse_defaults(self):
        self.opt_test("", [], {})

    def test_opt_parse_short_flag(self):
        self.opt_test("-a", [], {"alpha":True})

    def test_opt_parse_short_flags_grouped(self):
        self.opt_test("-ab", [], {"alpha":True, "bravo":False})

    def test_opt_parse_short_option(self):
        self.opt_test("-c ARG", [], {"charlie":self.opt_c.return_value})

    def test_opt_parse_short_enumerated(self):
        self.opt_test("-d 00", [], {"delta":1})

    def test_opt_parse_short_list(self):
        self.opt_test("-e0 -e1", [], {"echo":[0, 1]})

    def test_opt_parse_long_flag(self):
        self.opt_test("--alpha", [], {"alpha":True})

    def test_opt_parse_long_option(self):
        self.opt_test("--charlie ARG", [], {"charlie":self.opt_c.return_value})

    def test_opt_parse_long_enumerated(self):
        self.opt_test("--delta 10", [], {"delta":3})

    def test_opt_parse_long_list(self):
        self.opt_test("--foxtrot a --foxtrot b", [], {"foxtrot":[1, 2]})

    def test_opt_parse_invalid_flag(self):
        self.assertRaises(error.CmdParseError, self.parse, "-Z")

    def test_opt_parse_invalid_option_int_arg(self):
        self.assertRaises(error.CmdParseError, self.parse, "-e ABC")

    def test_opt_parse_invalid_option_enum_arg(self):
        self.assertRaises(error.CmdParseError, self.parse, "--foxtrot e")

    def test_cmd_parse_simple(self):
        self.cmd_test("cmd1", {}, self.command1, [], {})

    def test_cmd_parse_argument(self):
        self.cmd_test("cmd1 arg1 arg2", {}, self.command1, ["arg1", "arg2"], {})

    def test_cmd_parse_short_flag(self):
        self.cmd_test("cmd1 -g", {}, self.command1, [], {"golf":True})

    def test_cmd_parse_short_option(self):
        self.cmd_test("cmd1 -h b", {}, self.command1, [], {"hotel":[2]})

    def test_cmd_parse_long_flag(self):
        self.cmd_test("cmd1 --golf", {}, self.command1, [], {"golf":True})

    def test_cmd_parse_long_option(self):
        self.cmd_test("cmd1 --hotel c", {}, self.command1, [], {"hotel":[3]})

    def test_cmd_parse_global_flag_before(self):
        self.cmd_test("-b cmd1 -g", {"bravo":False}, self.command1, [], {"golf":True})

    def test_cmd_parse_global_flag_after(self):
        self.cmd_test("cmd1 -b -g", {"bravo":False}, self.command1, [], {"golf":True})

    def test_cmd_parse_global_option_before(self):
        self.cmd_test("--delta 00 cmd1 -g -h a", {"delta":1}, self.command1, [], {"golf":True, "hotel":[1]})

    def test_cmd_parse_global_option_after(self):
        self.cmd_test("cmd1 --delta 00 -g -h a", {"delta":1}, self.command1, [], {"golf":True, "hotel":[1]})

    def test_cmd_parse_overridden_before(self):
        self.cmd_test("-a cmd1 -g", {"alpha":True}, self.command1, [], {"golf":True})

    def test_cmd_parse_overriden_after(self):
        self.cmd_test("cmd1 -g -a 2", {}, self.command1, [], {"alpha":2, "golf":True})

    def test_cmd_parse_overridden_both(self):
        self.cmd_test("-a cmd1 -a401", {"alpha":True}, self.command1, [], {"alpha":401})

    def test_cmd_parse_alias(self):
        self.cmd_test("command1", {}, self.command1, [], {})

    def test_cmd_parse_unknown_command(self):
        self.assertRaises(error.CmdParseError, self.parse, "test-cmd")

