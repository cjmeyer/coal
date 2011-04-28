# test_command.py


import coal
import mock
import unittest2 as unittest

from coal import command, error
from coal.command import Command, opt


class CommandOptTest(unittest.TestCase):
    def setUp(self):
        self.opt_c = mock.Mock()
        self.opt_f = mock.Mock()
        self.parse_args = mock.Mock()
        self.opt_c.return_value = mock.Mock()

        class TestCommand1(Command):
            opts = [
                opt('alpha', 'a', store=True),
                opt('bravo', 'b', store=True),
                opt('charlie', 'c', store=self.opt_c),
                opt('delta', 'd', store={'00':1, '01':2, '10':3, '11':4}),
                opt('echo', 'e', store=int),
                opt('fox-trot', 'f')
            ]
            def opt_fox_trot(self_, arg):
                try:
                    self_['fox-trot'].append(arg)
                except:
                    self_['fox-trot'] = [arg]
            def parse_args(self_, *args):
                self.parse_args(*args)

        self.cmd = TestCommand1()

    def _test(self, cmd, args_, opts_):
        opts = {
            'alpha':None,
            'bravo':None,
            'charlie':None,
            'delta':None,
            'echo':None,
            'fox-trot':None }
        opts.update(opts_)
        self.cmd.parse(cmd.split())
        self.assertEqual(self.cmd.options, opts)
        self.parse_args.assert_called_once_with(*args_)

    def test_opt_parse_empty(self):
        self._test('', [], {})

    def test_opt_parse_args(self):
        self._test('arg1 arg2', ['arg1', 'arg2'], {})

    def test_opt_parse_short_flag(self):
        self._test('-a', [], {'alpha':True})

    def test_opt_parse_short_flags_grouped(self):
        self._test('-ab', [], {'alpha':True, 'bravo':True})

    def test_opt_parse_short_option(self):
        self._test('-c ARG', [], {'charlie':self.opt_c.return_value})

    def test_opt_parse_short_enumeration(self):
        self._test('-d 00', [], {'delta':1})

    def test_opt_parse_short_custom(self):
        self._test('-fARG1 -fARG2', [], {'fox-trot':['ARG1', 'ARG2']})

    def test_opt_parse_long_flag(self):
        self._test('--alpha', [], {'alpha':True})

    def test_opt_parse_long_option(self):
        self._test('--charlie ARG', [], {'charlie':self.opt_c.return_value})

    def test_opt_parse_long_enumeration(self):
        self._test('--delta 10', [], {'delta':3})

    def test_opt_parse_long_custom(self):
        self._test('--fox-trot ARG1 --fox-trot ARG2', [], {'fox-trot':['ARG1', 'ARG2']})

    def test_opt_parse_invalid_flag(self):
        pass

    def test_opt_parse_invalid_option_arg_int(self):
        pass

    def test_opt_parse_invalid_option_arg_enumeration(self):
        pass


class CommandSubCmdTest(unittest.TestCase):
    def setUp(self):
        class SubSubCommand1(Command):
            opts = [
                opt('echo', 'e', store=str),
                opt('fox-trot', 'f', store=True) ]

        class SubCommand1(Command):
            cmds = {
                'cmd1-1':SubSubCommand1 }
            opts = [
                opt('charlie', 'c', store=True),
                opt('delta', 'd', store=float),
                opt('echo', 'e', store={'a':4, 'b':3, 'c':2, 'd':1}) ]

        class SubCommand2(Command):
            opts = [
                opt('charlie', 'c', store=False),
                opt('delta', 'd', store=str),
                opt('golf', 'g', store=int) ]

        class AppCommand(Command):
            cmds = {
                'cmd1|command1':SubCommand1,
                'cmd2|command2':SubCommand2 }
            opts = [
                opt('alpha', 'a', store=True),
                opt('bravo', 'b', store=int),
                opt('charlie', 'c', store=1),
                opt('delta', 'd', store=str) ]

    def _test(self):
        pass

    def test_cmd_parse_simple(self):
        pass

    def test_cmd_parse_args(self):
        pass

    def test_cmd_parse_short_flag(self):
        pass

    def test_cmd_parse_short_option(self):
        pass

    def test_cmd_parse_long_flag(self):
        pass

    def test_cmd_parse_long_option(self):
        pass

    def test_cmd_parse_global_flag_before(self):
        pass

    def test_cmd_parse_global_flag_after(self):
        pass

    def test_cmd_parse_global_option_before(self):
        pass

    def test_cmd_parse_global_option_after(self):
        pass

    def test_cmd_parse_overridden_before(self):
        pass

    def test_cmd_parse_overridden_after(self):
        pass

    def test_cmd_parse_overridden_both(self):
        pass

    def test_cmd_parse_aliases(self):
        pass

    def test_cmd_parse_subsubcommand(self):
        pass

    def test_cmd_parse_unknown_command(self):
        pass

