# test_shell.py


import StringIO
import unittest2 as unittest

from hydra import minirst, util
from hydra.shell import Shell, ColorShell

from mock import Mock, patch


class ShellBaseTest(unittest.TestCase):
    def build_shell(self, stdin, stdout, stderr):
        return Shell(stdin, stdout, stderr)

    def setUp(self):
        self._stdin = StringIO.StringIO()
        self._stdout = StringIO.StringIO()
        self._stderr = StringIO.StringIO()

        self.shell = self.build_shell(self._stdin, self._stdout, self._stderr)

    def tearDown(self):
        pass

    @property
    def stdin(self):
        return self._stdin.getvalue()

    @stdin.setter
    def stdin(self, value):
        self._stdin.seek(0)
        self._stdin.truncate(0)
        self._stdin.write(value)
        self._stdin.seek(0)

    @property
    def stdout(self):
        s = self._stdout.getvalue()
        self._stdout.seek(0)
        self._stdout.truncate(0)
        return s

    @property
    def stderr(self):
        s = self._stderr.getvalue()
        self._stderr.seek(0)
        self._stderr.truncate(0)
        return s


class ShellTest(ShellBaseTest):
    def test_write(self):
        self.shell.write("Hello World!")
        self.assertEqual(self.stdout, "Hello World!")

    def test_write_all_keywords(self):
        self.shell.write("Hello World!", keyword1=1, keyword2=2, keyword3=3)

    def test_write_with_indent(self):
        self.shell.indent = 2
        self.shell.write("Hello World!")
        self.assertEqual(self.stdout, "  Hello World!")

    def test_write_err(self):
        self.shell.write_err("ERROR!")
        self.assertEqual(self.stderr, "ERROR!")

    def test_write_err_all_keywords(self):
        self.shell.write_err("ERROR!", keyword1=1, keyword2=2, keyword3=3)
        
    def test_write_err_with_indent(self):
        self.shell.indent = 2
        self.shell.write("ERROR!")
        self.assertEqual(self.stdout, "  ERROR!")

    def test_prompt(self):
        self.stdin = "Bob Jones\n"
        self.assertEqual(self.shell.prompt("What is your name? "), "Bob Jones")
        self.assertEqual(self.stdout, "What is your name? ")

    def test_prompt_default(self):
        self.stdin = "\n"
        self.assertEqual(self.shell.prompt("Are you sure [Y/n]: ", default="Y"), "Y")
        self.assertEqual(self.stdout, "Are you sure [Y/n]: ")

    def test_prompt_empty(self):
        self.stdin = "123\n"
        self.assertEqual(self.shell.prompt(), "123")
        self.assertEqual(self.stdout, "")

    def test_choose(self):
        self.stdin = "a\n"
        self.assertEqual(self.shell.choose("Which one? ", ["a", "b", "c"]), "a")
        self.assertEqual(self.stdout, "Which one? ")

    def test_choose_empty_with_default(self):
        self.stdin = "\n"
        self.assertEqual(self.shell.choose("Which one? ", ["a", "b", "c"], default="a"), "a")
        self.assertEqual(self.stdout, "Which one? ")

    def test_choose_first_empty_no_default(self):
        self.stdin = "\nb\n"
        self.assertEqual(self.shell.choose("Which one? ", ["a", "b", "c"]), "b")
        self.assertEqual(self.stdout, "Which one? Which one? ")

    def test_choose_first_invalid(self):
        self.stdin = "z\na\n"
        self.assertEqual(self.shell.choose("Which one? ", ["a", "b", "c"]), "a")
        self.assertEqual(self.stdout, "Which one? Invalid choice\nWhich one? ")

    def test_choose_case_insensitive(self):
        self.stdin = "C\n"
        self.assertEqual(self.shell.choose("Which one? ", ["a", "b", "c"]), "c")
        self.assertEqual(self.stdout, "Which one? ")

        self.stdin = "c\n"
        self.assertEqual(self.shell.choose("Which one? ", ["a", "b", "C"]), "C")
        self.assertEqual(self.stdout, "Which one? ")

    def test_choose_case_sensitive(self):
        self.stdin = "a\nA\n"
        self.assertEqual(self.shell.choose("Which one? ", ["A", "b", "c"], case_sensitive=True), "A")
        self.assertEqual(self.stdout, "Which one? Invalid choice\nWhich one? ")

        self.stdin = "A\na\n"
        self.assertEqual(self.shell.choose("Which one? ", ["a", "b", "c"], case_sensitive=True), "a")
        self.assertEqual(self.stdout, "Which one? Invalid choice\nWhich one? ")

    def test_diff(self):
        left = "one\ntwo\nthree\n"
        right = "one\nTWO\nthree\n"
        diff = ["--- left",
                "+++ right",
                "@@ -1,3 +1,3 @@",
                " one",
                "-two",
                "+TWO",
                " three"]

        self.shell.diff(left, right, "left", "right")

        for l in self.stdout.splitlines():
            self.assertEqual(l.rstrip(), diff.pop(0))

    def _test_output_option(self, attr_name, value, fn_name, msg, expected):
        setattr(self.shell, attr_name, value)
        getattr(self.shell, fn_name)(msg)
        self.assertEqual(self.stdout, expected)

    def test_debug_off(self):
        self._test_output_option("debug_on", False, "debug", "Debug 1", "")

    def test_debug_on(self):
        self._test_output_option("debug_on", True, "debug", "Debug 2", "Debug 2")

    def test_note_verbose_off(self):
        self._test_output_option("verbose", False, "note", "Note 1", "")

    def test_note_verbose_on(self):
        self._test_output_option("verbose", True, "note", "Note 2", "Note 2")

    def test_status_quiet_off(self):
        self._test_output_option("quiet", False, "status", "Status 1", "Status 1")

    def test_status_quiet_on(self):
        self._test_output_option("quiet", True, "status", "Status 2", "")

    def test_warn(self):
        self.shell.warn("Warn 1")
        self.assertEqual(self.stderr, "Warn 1")

    def test_debug_default(self):
        self.assertEqual(self.shell.debug_on, False)

    def test_verbose_default(self):
        self.assertEqual(self.shell.verbose, False)

    def test_quiet_default(self):
        self.assertEqual(self.shell.quiet, False)

    def test_indent_default(self):
        self.assertEqual(self.shell.indent, 0)

    def _test_output_kw_options(self, fn_name, wr_name):
        with patch.object(self.shell, wr_name) as write:
            kw1 = Mock()
            kw2 = Mock()
            kw3 = Mock()
            getattr(self.shell, fn_name)("Message", kw1=kw1, kw2=kw2, kw3=kw3)
            write.assert_called_once_with("Message", kw1=kw1, kw2=kw2, kw3=kw3)

    def test_debug_kw_options(self):
        self.shell.debug_on = True
        self._test_output_kw_options("debug", "write")

    def test_note_kw_options(self):
        self.shell.verbose = True
        self._test_output_kw_options("note", "write")

    def test_status_kw_options(self):
        self._test_output_kw_options("status", "write")

    def test_warn_kw_options(self):
        self._test_output_kw_options("warn", "write_err")


class ShellTermWidthTest(ShellBaseTest):
    @patch.object(util, "termwidth")
    def test_termwidth(self, termwidth):
        termwidth.return_value = Mock()

        self.assertEqual(self.shell.termwidth(), termwidth.return_value)
        termwidth.assert_called_once_with()

    def test_termwidth_override(self):
        self.shell.width = Mock()
        self.assertEqual(self.shell.termwidth(), self.shell.width)


class ShellRSTFormatTest(ShellBaseTest):
    @patch.object(minirst, "format_rst")
    def test_rst_default_width(self, format):
        with patch.object(self.shell, "termwidth") as width:
            width.return_value = 33

            self.shell.rst("RST source text")

            width.assert_called_once_with()
            format.assert_called_once_with("RST source text", indent="", width=31, keep=[])

    @patch.object(minirst, "format_rst")
    def test_rst_with_width(self, format):
        self.shell.rst("RST source text", width=80)
        format.assert_called_once_with("RST source text", indent="", width=80, keep=[])

    @patch.object(minirst, "format_rst")
    def test_rst_with_verbose_on(self, format):
        self.shell.verbose = True
        self.shell.rst("RST source text", width=80)
        format.assert_called_once_with("RST source text", indent="", width=80, keep=["verbose"])

    @patch.object(minirst, "format_rst")
    def test_rst_with_keep(self, format):
        keep = [Mock()]

        self.shell.verbose = True
        self.shell.rst("RST source text", width=80, keep=keep)

        format.assert_called_once_with("RST source text", indent="", width=80, keep=[keep[0], "verbose"])


class ColorShellTest(ShellTest):
    def build_shell(self, stdin, stdout, stderr):
        return ColorShell(stdin, stdout, stderr)

    def test_write_without_color(self):
        self.shell.write("Hello World!")
        self.assertEqual(self.stdout, "Hello World!")

    def test_write_with_plain_red(self):
        self.shell.write("Hello World!", color="red")
        self.assertEqual(self.stdout, "\033[31mHello World!\033[0m")

    def test_write_with_plain_green(self):
        self.shell.write("Hello World!", color="green")
        self.assertEqual(self.stdout, "\033[32mHello World!\033[0m")

    def test_write_with_plain_yellow(self):
        self.shell.write("Hello World!", color="yellow")
        self.assertEqual(self.stdout, "\033[33mHello World!\033[0m")

    def test_write_with_plain_blue(self):
        self.shell.write("Hello World!", color="blue")
        self.assertEqual(self.stdout, "\033[34mHello World!\033[0m")

    def test_write_with_plain_white(self):
        self.shell.write("Hello World!", color="white")
        self.assertEqual(self.stdout, "\033[37mHello World!\033[0m")

    def test_write_with_bold_red(self):
        self.shell.write("Hello World!", color="*red*")
        self.assertEqual(self.stdout, "\033[1m\033[31mHello World!\033[0m")

    def test_write_with_italic_green(self):
        self.shell.write("Hello World!", color="/green/")
        self.assertEqual(self.stdout, "\033[3m\033[32mHello World!\033[0m")

    def test_write_with_underline_yellow(self):
        self.shell.write("Hello World!", color="_yellow_")
        self.assertEqual(self.stdout, "\033[4m\033[33mHello World!\033[0m")

    def test_write_with_strike_blue(self):
        self.shell.write("Hello World!", color="-blue-")
        self.assertEqual(self.stdout, "\033[9m\033[34mHello World!\033[0m")

    def test_diff(self):
        pass

    def test_diff(self):
        left = "one\ntwo\nthree\n"
        right = "one\nTWO\nthree\n"

        expected = [
            "\033[1m\033[31m--- left",
            "\033[0m\033[1m\033[32m+++ right",
            "\033[0m\033[1m\033[37m@@ -1,3 +1,3 @@",
            "\033[0m one",
            "\033[1m\033[31m-two",
            "\033[0m\033[1m\033[32m+TWO",
            "\033[0m three"]

        self.shell.diff(left, right, "left", "right")
        for l in self.stdout.splitlines():
            self.assertEqual(l.strip(), expected.pop(0).strip())

