# test_options.py


import coal
import mock
import os
import unittest2 as unittest

from coal import error, Opt, Options

from mock import patch


class OptionsOptTest(unittest.TestCase):
    def setUp(self):
        self.opt_c = mock.Mock()
        self.opt_f = mock.Mock()
        self.parse_args = mock.Mock()
        self.opt_c.return_value = mock.Mock()

        class TestOptions1(Options):
            opts = [
                Opt('alpha', 'a', store=True),
                Opt('bravo', 'b', store=True),
                Opt('charlie', 'c', store=self.opt_c),
                Opt('delta', 'd', store={'00':1, '01':2, '10':3, '11':4}),
                Opt('echo', 'e', store=int),
                Opt('fox-trot', 'f', handler='fox_trot')
            ]
            def fox_trot(self_, arg):
                try:
                    self_['fox-trot'].append(arg)
                except:
                    self_['fox-trot'] = [arg]
            def parse_args(self_, *args):
                self.parse_args(*args)

        self.cmd = TestOptions1()

    def parse(self, cmd):
        self.cmd.parse(cmd.split())

    def _test(self, cmd, args_, opts_):
        opts = {
            'alpha':None,
            'bravo':None,
            'charlie':None,
            'delta':None,
            'echo':None,
            'fox-trot':None }
        opts.update(opts_)
        self.parse(cmd)
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
        self.assertRaises(error.OptionsError, self.parse, '--zulu')

    def test_opt_parse_invalid_option_arg_int(self):
        self.assertRaises(error.OptionsError, self.parse, '-eARG')

    def test_opt_parse_invalid_option_arg_enumeration(self):
        self.assertRaises(error.OptionsError, self.parse, '--delta=123')


class OptionsSubCmdTest(unittest.TestCase):
    def setUp(self):
        self.sub_sub_command1 = mock.Mock()
        self.sub_command1 = mock.Mock()
        self.sub_command2 = mock.Mock()
        self.app_command = mock.Mock()

        self.post_actions = []

        def post_action(self_):
            self.post_actions.append(self_.name)
        
        def parse_args(handler):
            def decorator(cls):
                cls.post_options = post_action
                cls.parse_args = getattr(self, handler)
                cls.name = handler
                return cls
            return decorator

        @parse_args('sub_sub_command1')
        class SubSubOptions1(Options):
            opts = [
                Opt('echo', 'e', store=str),
                Opt('fox-trot', 'f', store=True) ]

        @parse_args('sub_command1')
        class SubOptions1(Options):
            cmds = {
                'cmd1-1':SubSubOptions1 }
            opts = [
                Opt('charlie', 'c', store=True),
                Opt('delta', 'd', store=float),
                Opt('echo', 'e', store={'a':4, 'b':3, 'c':2, 'd':1}) ]

        @parse_args('sub_command2')
        class SubOptions2(Options):
            opts = [
                Opt('charlie', 'c', store=False),
                Opt('delta', 'd', store=str),
                Opt('golf', 'g', store=True),
                Opt('hotel', 'h', store=int) ]

        @parse_args('app_command')
        class AppOptions(Options):
            cmds = {
                'cmd1|command1':SubOptions1,
                'cmd2|command2':SubOptions2 }
            opts = [
                Opt('alpha', 'a', store=True),
                Opt('bravo', 'b', store=int),
                Opt('charlie', 'c', store=1),
                Opt('delta', 'd', store=str) ]

        self.app = AppOptions()

    def parse(self, cmd):
        self.app.parse(cmd.split())

    def _verify(self, cmd, args, opts, subcmds):
        for key, val in opts.iteritems():
            self.assertEqual(cmd[key], val)
        if not subcmds:
            getattr(self, cmd.name).assert_called_once_with(*args)
        else:
            self.assertEqual(cmd.subcmd.name, subcmds[0][0])
            self._verify(cmd.subcmd, args, subcmds[0][1], subcmds[1:])

    def _test(self, cmd, args, opts, *subcmds):
        post_actions = ['app_command'] + [c[0] for c in subcmds]
        self.parse(cmd)
        self._verify(self.app, args, opts, subcmds)
        self.assertEqual(self.post_actions, post_actions)

    def test_cmd_parse_no_subcommand(self):
        self._test('-cb 645', [], {'charlie':1, 'bravo':645})

    def test_cmd_parse_simple(self):
        self._test('cmd2', [], {}, ('sub_command2', {}))

    def test_cmd_parse_args(self):
        self._test('cmd2 arg1 arg2', ['arg1', 'arg2'], {}, ('sub_command2', {}))

    def test_cmd_parse_short_flag(self):
        self._test('cmd2 -g', [], {}, ('sub_command2', {'golf':True}))

    def test_cmd_parse_short_option(self):
        self._test('cmd2 -h 101', [], {}, ('sub_command2', {'hotel':101}))

    def test_cmd_parse_long_flag(self):
        self._test('cmd2 --golf', [], {}, ('sub_command2', {'golf':True}))

    def test_cmd_parse_long_option(self):
        self._test('cmd2 --hotel 321', [], {}, ('sub_command2', {'hotel':321}))

    def test_cmd_parse_global_flag_before(self):
        self._test('-a cmd2', [], {'alpha':True}, ('sub_command2', {}))

    def test_cmd_parse_global_flag_after(self):
        self._test('cmd2 -a', [], {'alpha':True}, ('sub_command2', {}))

    def test_cmd_parse_global_option_before(self):
        self._test('-b 101 cmd2', [], {'bravo':101}, ('sub_command2', {}))

    def test_cmd_parse_global_option_after(self):
        self._test('cmd2 -b 123', [], {'bravo':123}, ('sub_command2', {}))

    def test_cmd_parse_overridden_before(self):
        self._test('-c cmd2', [], {'charlie':1}, ('sub_command2', {}))

    def test_cmd_parse_overridden_after(self):
        self._test('cmd2 -c', [], {}, ('sub_command2', {'charlie':False}))

    def test_cmd_parse_overridden_both(self):
        self._test('-c cmd2 -c', [], {'charlie':1}, ('sub_command2', {'charlie':False}))

    def test_cmd_parse_aliases(self):
        self._test('command2', [], {}, ('sub_command2', {}))

    def test_cmd_parse_subsubcommand(self):
        self._test('cmd1 cmd1-1', [], {}, ('sub_command1', {}), ('sub_sub_command1', {}))

    def test_cmd_parse_subsubcommand_args_and_options(self):
        self._test('-c cmd1 -e a cmd1-1 arg1 -d 1.0 -a -e Hello', ['arg1'], {'charlie':1},
                ('sub_command1', {'delta':1.0, 'echo':4}),
                ('sub_sub_command1', {'echo':'Hello'}))

    def test_cmd_parse_unknown_command(self):
        self.assertRaises(error.OptionsError, self.parse, 'cmd3')


class OptionsInheritanceTest(unittest.TestCase):
    def setUp(self):
        class BaseOptions(Options):
            opts = [
                Opt('alpha', 'a', store=True),
                Opt('bravo', 'b', store=int) ]

        class TestOptions(BaseOptions):
            opts = [
                Opt('charlie', 'c', store=True),
                Opt('delta', 'd', store=str) ]

        self.cmd = TestOptions()

    def parse(self, cmd):
        self.cmd.parse(cmd.split())

    def _test(self, cmd, opts):
        self.parse(cmd)
        for key, val in opts.iteritems():
            self.assertEqual(self.cmd[key], val)

    def test_non_base_flag(self):
        self._test('--charlie', {'charlie':True})

    def test_non_base_option(self):
        self._test('-d ARG', {'delta':'ARG'})

    def test_base_flag(self):
        self._test('-a', {'alpha':True})

    def test_base_option(self):
        self._test('-b873', {'bravo':873})


from test_shell import ShellBaseTest


class OptionsHelpTest(ShellBaseTest):
    def setUp(self):
        ShellBaseTest.setUp(self)

        class TestSubOptions(Options):
            desc = """
                short sub-command description string

                Long sub-command description string.
                """
            usage = '[options]'
            opts = [
                Opt('alpha', 'a', 'alpha help string', store=int),
                Opt('echo', 'e', 'echo help string', store=True),
                Opt('foxtrot', '', 'foxtrot help string', store=str) ]

        class TestOptions(Options):
            desc = """
                short command description string

                Long command description string.
                """
            usage = '[options]'
            cmds = {
                'subcmd|sub-command':TestSubOptions }
            opts = [
                Opt('alpha', 'a', 'alpha help string', store=True),
                Opt('bravo', 'b', 'bravo help string', store=int, metavar='INT'),
                Opt('charlie', '', 'charlie help string', store=True),
                Opt('delta', '', 'delta help string', store=str) ]

        self.ui = self.shell
        self.cmd = TestOptions(name='cmd', ui=self.ui)

    def tearDown(self):
        ShellBaseTest.tearDown(self)

    def _test(self, cmd, fname, *args, **opts):
        cmd.help(*args, **opts)
        fname = os.path.join(os.path.dirname(__file__), 'help', fname)
        self.assertEqual(self.stdout.splitlines(), open(fname).read().splitlines())

    def test_help_command_normal(self):
        self._test(self.cmd, 'cmd_normal.t')

    def test_help_sub_command_normal(self):
        self._test(self.cmd.findcmd('subcmd'), 'subcmd_normal.t')

