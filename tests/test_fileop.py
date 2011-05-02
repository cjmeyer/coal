# test_fileop.py


import coal
import os
import mock
import shutil
import stat
import StringIO
import unittest2 as unittest

from mock import patch

from coal import error, shell
from coal.fileop import FileOp


def mkdir(p):
    if not os.path.exists(p):
        os.makedirs(p, 0755)
    elif not os.path.isdir(p):
        raise Exception("Path already exists but is not a directory")

def make_file(p):
    mkdir(os.path.dirname(p))
    return open(p, "w")

def read(p):
    with open(p, "r") as f:
        return f.read()

_conflict_msg = (
        "How do you wish to proceed with this file?\n"
        "over(w)rite, (s)kip, (r)ender, (d)iff, (a)bort: ")


class FileOpBaseHelper(unittest.TestCase):
    def build_shell(self, stdin, stdout, stderr):
        return shell.Shell(stdin, stdout, stderr)

    def build_fop(self, shell_, srcroot, dstroot):
        return FileOp(shell_, srcroot, dstroot)

    def setUp(self):
        self.basepath = os.path.abspath(os.path.dirname(__file__))
        self.srcroot = os.path.join(self.basepath, "templates")
        self.dstroot = os.path.join(self.basepath, "results")
        self._stdin = StringIO.StringIO()
        self._stdout = StringIO.StringIO()
        self._stderr = StringIO.StringIO()

        self.shell = self.build_shell(self._stdin, self._stdout, self._stderr)
        self.act = self.build_fop(self.shell, self.srcroot, self.dstroot)

        if os.path.exists(self.dstroot):
            shutil.rmtree(self.dstroot, ignore_errors=True)

        os.makedirs(self.dstroot, 0755)

    def tearDown(self):
        if os.path.exists(self.dstroot):
            shutil.rmtree(self.dstroot, ignore_errors=True)

    def src(self, p):
        return os.path.join(self.srcroot, p)

    def dst(self, p):
        return os.path.join(self.dstroot, p)

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


class FileOpPathExpansionTest(FileOpBaseHelper):
    def test_expand_src_abspath(self):
        self.assertEqual(self.act.expandsrc("/path/to/src"), self.src("/path/to/src"))

    def test_expand_src_relpath(self):
        self.assertEqual(self.act.expandsrc("path/to/src"), self.src("path/to/src"))

    def test_expand_dst_abspath(self):
        self.assertEqual(self.act.expanddst("/path/to/dst"), self.dst("/path/to/dst"))

    def test_expand_dst_relpath(self):
        self.assertEqual(self.act.expanddst("path/to/dst"), self.dst("path/to/dst"))

    def test_expand_dst_simple_pattern(self):
        self.act.foo = "bar"
        self.assertEqual(self.act.expanddst("path/to/%foo%.txt"), self.dst("path/to/bar.txt"))

    def test_expand_dst_complext_pattern(self):
        self.act.foo = "bar"
        self.assertEqual(self.act.expanddst("path/to/%%_%%%foo%_%%.txt"), self.dst("path/to/%_%bar_%.txt"))


class FileOpStatusHelper(FileOpBaseHelper):
    def setUp(self):
        FileOpBaseHelper.setUp(self)
        self.shell.status = mock.Mock()

    def assert_status(self, msg, p, color=None):
        if os.path.isabs(p):
            p = os.path.relpath(p)
        self.assertEqual(self.shell.status.call_args_list.pop(0), ((msg.rjust(12),), {"color":color}))
        self.assertEqual(self.shell.status.call_args_list.pop(0), (("  %s\n" % p,), {}))


class FileOpStatusTest(FileOpStatusHelper):
    def test_status_plain(self):
        self.act.status("status", "path/to/file")
        self.assert_status("status", "path/to/file")

    def test_status_color(self):
        self.act.status("status", "/path/to/file", color=id(self))
        self.assert_status("status", "/path/to/file", color=id(self))


class FileOpInsideTest(FileOpStatusHelper):
    def test_inside_relative_dir(self):
        with self.act.inside("path/to/dir"):
            self.assertEqual(self.act.dstroot, self.dst("path/to/dir"))
        self.assertEqual(self.act.dstroot, self.dstroot)

    def test_inside_absolute_dir(self):
        with self.act.inside("/path/to/dir"):
            self.assertEqual(self.act.dstroot, self.dst("/path/to/dir"))
        self.assertEqual(self.act.dstroot, self.dstroot)


class FileOpDirectoryTest(FileOpStatusHelper):
    def directory(self, dst, revoke=False, pretend=False, chmod=None):
        self.act.revoke = revoke
        self.act.pretend = pretend
        self.act.directory(dst, chmod=chmod)

    def test_invoke(self):
        self.directory("path/to/dir")
        self.assertTrue(os.path.isdir(self.dst("path/to/dir")))

    def test_invoke_pretend(self):
        self.directory("path/to/dir", pretend=True)
        self.assertFalse(os.path.exists(self.dst("path/to/dir")))

    def test_invoke_status_create(self):
        self.directory("path/to/dir")
        self.assert_status("create", self.dst("path/to/dir"), color="*green*")

    def test_invoke_status_exists(self):
        mkdir(self.dst("path/to/dir"))
        self.directory("path/to/dir")
        self.assert_status("exist", self.dst("path/to/dir"), color="*blue*")

    def test_revoke(self):
        mkdir(self.dst("path/to/dir"))
        self.directory("path/to/dir", revoke=True)
        self.assertFalse(os.path.exists(self.dst("path/to/dir")))

    def test_revoke_status(self):
        mkdir(self.dst("path/to/dir"))
        self.directory("path/to/dir", revoke=True)
        self.assert_status("remove", self.dst("path/to/dir"), color="*red*")

    def test_revoke_pretend(self):
        mkdir(self.dst("path/to/dir"))
        self.directory("path/to/dir", revoke=True, pretend=True)
        self.assertTrue(os.path.isdir(self.dst("path/to/dir")))

    def test_revoke_pretend_status(self):
        mkdir(self.dst("path/to/dir"))
        self.directory("path/to/dir", revoke=True, pretend=True)
        self.assert_status("remove", self.dst("path/to/dir"), color="*red*")

    def revoke_not_empty(self):
        with make_file(self.dst("path/to/dir/file.txt")) as f:
            f.write("a file")
        self.directory("path/to/dir", revoke=True)

    def test_revoke_not_empty(self):
        self.revoke_not_empty()
        self.assertTrue(os.path.isdir(self.dst("path/to/dir")))

    def test_revoke_not_empty_status(self):
        self.revoke_not_empty()
        self.assertEqual(self.stdout, "")


class FileOpFileTest(FileOpStatusHelper):
    def _file(self, src, dst, chmod=None):
        self.act.file(src, dst, chmod=chmod)

    def file(self, src, dst, chmod=None, pretend=False, force=False, skip=False, revoke=False):
        self.act.pretend = pretend
        self.act.force = force
        self.act.skip = skip
        self.act.revoke = revoke
        self._file(src, dst, chmod=chmod)

    def test_invoke(self):
        self.file("source1.txt", "path/to/result.txt")
        self.assertEqual(read(self.src("source1.txt")), read(self.dst("path/to/result.txt")))

    def test_invoke_chmod_same(self):
        self.file("source1.txt", "path/to/result.txt")
        self.assertEqual(os.stat(self.src("source1.txt")).st_mode, os.stat(self.dst("path/to/result.txt")).st_mode)

    def test_invoke_chmod_0777(self):
        self.file("source1.txt", "path/to/result2.txt", chmod=0777)
        self.assertEqual(stat.S_IMODE(os.stat(self.dst("path/to/result2.txt")).st_mode), 0777)

    def test_invoke_chmod_0644(self):
        self.file("source1.txt", "path/to/result3.txt", chmod=0644)
        self.assertEqual(stat.S_IMODE(os.stat(self.dst("path/to/result3.txt")).st_mode), 0644)

    def test_invoke_pretend(self):
        self.file("source1.txt", "path/to/result.txt", pretend=True)
        self.assertFalse(os.path.exists(self.dst("path/to/result.txt")))

    def test_invoke_status_create(self):
        self.file("source1.txt", "path/to/result.txt")
        self.assert_status("create", self.dst("path/to/result.txt"), color="*green*")

    def _invoke_conflict(self, contents, **kw):
        with make_file(self.dst("path/to/result.txt")) as f:
            f.write(contents)
        self.file("source1.txt", "path/to/result.txt", **kw)

    def test_invoke_status_identical(self):
        self._invoke_conflict("source 1\n")
        self.assert_status("identical", self.dst("path/to/result.txt"), color="*blue*")

    def test_invoke_skip(self):
        self._invoke_conflict("conflict", skip=True)
        self.assertEqual(read(self.dst("path/to/result.txt")), "conflict")

    def test_invoke_skip_status(self):
        self._invoke_conflict("conflict", skip=True)
        self.assert_status("skip", self.dst("path/to/result.txt"), color="*yellow*")

    def test_invoke_force(self):
        self._invoke_conflict("conflict", force=True)
        self.assertEqual(read(self.src("source1.txt")), read(self.dst("path/to/result.txt")))

    def test_invoke_force_status(self):
        self._invoke_conflict("conflict", force=True)
        self.assert_status("force", self.dst("path/to/result.txt"), color="*yellow*")

    def _conflict(self, *choices):
        with make_file(self.dst("path/to/result.txt")) as f:
            f.write("conflict")
        self.stdin = "\n".join(choices) + "\n"
        self.file("source1.txt", "path/to/result.txt")
        self.assert_status("conflict", self.dst("path/to/result.txt"), color="*red*")

    def test_invoke_conflict_overwrite(self):
        self._conflict("w")
        self.assertEqual(read(self.dst("path/to/result.txt")), read(self.src("source1.txt")))
        self.assertEqual(self.stdout, _conflict_msg + "Overwritten\n")

    def test_invoke_conflict_skip(self):
        self._conflict("s")
        self.assertEqual(read(self.dst("path/to/result.txt")), "conflict")
        self.assertEqual(self.stdout, _conflict_msg + "Skipped\n")

    def test_invoke_conflict_abort(self):
        self.assertRaises(error.AbortError, self._conflict, "a")
        self.assert_status("conflict", self.dst("path/to/result.txt"), color="*red*")

    def test_invoke_conflict_menu(self):
        self._conflict("r", "d", "w")

        dst = os.path.relpath(self.dst("path/to/result.txt"))
        expected = "".join([_conflict_msg, "Rendering %s\n" % dst,
                            "\n",
                            "source 1\n",
                            "\n",
                            _conflict_msg, "Showing differences for %s\n" % dst,
                            "\n",
                            "--- old\n",
                            "+++ new\n",
                            "@@ -1,1 +1,1 @@\n",
                            "-conflict\n",
                            "+source 1\n",
                            "\n",
                            _conflict_msg, "Overwritten"]).splitlines()

        for l in self.stdout.splitlines():
            self.assertEqual(l.strip(), expected.pop(0).strip())

    def _revoke(self, **kw):
        with make_file(self.dst("path/to/result.txt")) as f:
            f.write("source 1\n")
        self.file("source1.txt", "path/to/result.txt", revoke=True, **kw)

    def test_revoke(self):
        self._revoke()
        self.assertFalse(os.path.exists(self.dst("path/to/result.txt")))

    def test_revoke_status(self):
        self._revoke()
        self.assert_status("remove", self.dst("path/to/result.txt"), color="*red*")

    def test_revoke_pretend(self):
        self._revoke(pretend=True)
        self.assertEqual(read(self.dst("path/to/result.txt")), "source 1\n")

    def test_revoke_pretend_status(self):
        self._revoke(pretend=True)
        self.assert_status("remove", self.dst("path/to/result.txt"), color="*red*")

    def test_revoke_not_present(self):
        self.file("source1.txt", "path/to/result.txt", revoke=True)
        self.assertEqual(self.shell.status.call_count, 0)


class FileOpMakeFileTest(FileOpStatusHelper):
    def file(self, content, dst, chmod=None, pretend=False, force=False, skip=False, revoke=False):
        self.act.pretend = pretend
        self.act.force = force
        self.act.skip = skip
        self.act.revoke = revoke

        with self.act.mkfile(dst, chmod=chmod) as f:
            f.write(content)

    def test_invoke_create(self):
        self.file("content", "path/to/result.txt")
        self.assertEqual(read(self.dst("path/to/result.txt")), "content")

    def test_invoke_chmod_0777(self):
        self.file("content", "path/to/result2.txt", chmod=0777)
        self.assertEqual(stat.S_IMODE(os.stat(self.dst("path/to/result2.txt")).st_mode), 0777)

    def test_invoke_chmod_0644(self):
        self.file("content", "path/to/result3.txt", chmod=0644)
        self.assertEqual(stat.S_IMODE(os.stat(self.dst("path/to/result3.txt")).st_mode), 0644)

    def test_invoke_pretend(self):
        self.file("content", "path/to/result.txt", pretend=True)
        self.assertFalse(os.path.exists(self.dst("path/to/result.txt")))

    def test_invoke_create_status(self):
        self.file("content", "path/to/result.txt")
        self.assert_status("create", self.dst("path/to/result.txt"), color="*green*")

    def _invoke_conflict(self, contents, **kw):
        with make_file(self.dst("path/to/result.txt")) as f:
            f.write(contents)
        self.file("content", "path/to/result.txt", **kw)

    def test_invoke_identical_status(self):
        self._invoke_conflict("content")
        self.assert_status("identical", self.dst("path/to/result.txt"), color="*blue*")

    def test_invoke_skip(self):
        self._invoke_conflict("conflict", skip=True)
        self.assertEqual(read(self.dst("path/to/result.txt")), "conflict")

    def test_invoke_skip_status(self):
        self._invoke_conflict("conflict", skip=True)
        self.assert_status("skip", self.dst("path/to/result.txt"), color="*yellow*")

    def test_invoke_force(self):
        self._invoke_conflict("conflict", force=True)
        self.assertEqual(read(self.dst("path/to/result.txt")), "content")

    def test_invoke_force_status(self):
        self._invoke_conflict("conflict", force=True)
        self.assert_status("force", self.dst("path/to/result.txt"), color="*yellow*")

    def _conflict(self, *choices):
        with make_file(self.dst("path/to/result.txt")) as f:
            f.write("conflict\n")
        self.stdin = "\n".join(choices) + "\n"
        self.file("content\n", "path/to/result.txt")
        self.assert_status("conflict", self.dst("path/to/result.txt"), color="*red*")

    def test_invoke_conflict_overwrite(self):
        self._conflict("w")
        self.assertEqual(read(self.dst("path/to/result.txt")), "content\n")
        self.assertEqual(self.stdout, _conflict_msg + "Overwritten\n")

    def test_invoke_conflict_skip(self):
        self._conflict("s")
        self.assertEqual(read(self.dst("path/to/result.txt")), "conflict\n")
        self.assertEqual(self.stdout, _conflict_msg + "Skipped\n")

    def test_invoke_conflict_abort(self):
        self.assertRaises(error.AbortError, self._conflict, "a")
        self.assertEqual(self.stdout, _conflict_msg)
        self.assert_status("conflict", self.dst("path/to/result.txt"), color="*red*")

    def test_invoke_conflict_menu(self):
        self._conflict("r", "d", "w")

        dst = os.path.relpath(self.dst("path/to/result.txt"))
        expected = "".join([_conflict_msg, "Rendering %s\n" % dst,
                            "\n",
                            "content\n",
                            "\n",
                            _conflict_msg, "Showing differences for %s\n" % dst,
                            "\n",
                            "--- old\n",
                            "+++ new\n",
                            "@@ -1,1 +1,1 @@\n",
                            "-conflict\n",
                            "+content\n",
                            "\n",
                            _conflict_msg, "Overwritten"]).splitlines()

        for l in self.stdout.splitlines():
            self.assertEqual(l.strip(), expected.pop(0).strip())

    def _revoke(self, **kw):
        with make_file(self.dst("path/to/result.txt")) as f:
            f.write("content")
        self.file("content", "path/to/result.txt", revoke=True, **kw)

    def test_revoke(self):
        self._revoke()
        self.assertFalse(os.path.exists(self.dst("path/to/result.txt")))

    def test_revoke_status(self):
        self._revoke()
        self.assert_status("remove", self.dst("path/to/result.txt"), color="*red*")

    def test_revoke_pretend(self):
        self._revoke(pretend=True)
        self.assertEqual(read(self.dst("path/to/result.txt")), "content")

    def test_revoke_pretend_status(self):
        self._revoke(pretend=True)
        self.assert_status("remove", self.dst("path/to/result.txt"), color="*red*")

    def test_revoke_not_present(self):
        self.file("content", "path/to/result.txt", revoke=True)
        self.assertEqual(self.shell.status.call_count, 0)


class FileOpTemplateTest(FileOpFileTest):
    def _file(self, src, dst, chmod=None):
        self.act.template(src, dst, chmod=chmod)

    def test_render_template(self):
        self.act.foo = "bar"
        self.file("source.t", "path/to/result.txt")
        self.assertEqual(read(self.dst("path/to/result.txt")), "bar\n")


class FileOpGlobTest(FileOpBaseHelper):
    def test_glob_directory(self):
        mkdir(self.src("template_dir/dir3"))

        files, templates, directories = {}, {}, {}

        def file(src, dst):
            files[os.path.normpath(dst)] = os.path.normpath(src)

        def template(src, dst):
            templates[os.path.normpath(dst)] = os.path.normpath(src)

        def directory(dst):
            directories[os.path.normpath(dst)] = None

        self.act.file = file
        self.act.template = template
        self.act.directory = directory

        a = self.act.glob("template_dir", "test_dir", templates=["*.t"])

        def test(l, p):
            src = self.src(os.path.join("template_dir", p))
            dst = self.dst(os.path.join("test_dir", p))
            self.assertTrue(dst in l)
            if l[dst] is not None:
                self.assertEqual(l[dst], src)
            del l[dst]

        test(files, "file1.txt")
        test(files, "dir1/file1.txt")
        test(files, "dir2/file1.txt")

        test(templates, "file2.t")
        test(templates, "dir1/file2.t")
        test(templates, "dir2/file2.t")

        test(directories, "dir3")

        self.assertTrue(not files)
        self.assertTrue(not templates)
        self.assertTrue(not directories)


class FileOpInjectTest(FileOpStatusHelper):
    def setUp(self):
        FileOpStatusHelper.setUp(self)

        with make_file(self.dst("doc/README.1")) as f:
            f.write("--start--\nREADME\n--end--\n")
        with make_file(self.dst("doc/README.2")) as f:
            f.write("--start--\ntext after\nREADME\ntext before\n--end--\n")
        with make_file(self.dst("doc/README.3")) as f:
            f.write("--start--\n1\n2\nREADME\n3\n4\n--end--\n")

    def inject(self, dst, txt, pretend=False, revoke=False, **kw):
        self.act.pretend = pretend
        self.act.revoke = revoke
        with self.act.inject(dst, **kw) as f:
            f.write(txt)

    def test_invoke_inject_after(self):
        self.inject("doc/README.1", "\ninjected", after="--start--")
        self.assertEqual(read(self.dst("doc/README.1")), "--start--\ninjected\nREADME\n--end--\n")

    def test_invoke_inject_before(self):
        self.inject("doc/README.1", "injected\n", before="--end--")
        self.assertEqual(read(self.dst("doc/README.1")), "--start--\nREADME\ninjected\n--end--\n")

    def test_invoke_inject_status(self):
        self.inject("doc/README.1", "injected\n", after="--start--")
        self.assert_status("update", self.dst("doc/README.1"), "*green*")

    def test_invoke_inject_before_and_after(self):
        self.assertRaises(error.ArgumentError, self.inject, "doc/README.1", "injected",
                before="--end--", after="--after--")

    def test_invoke_inject_pretend(self):
        self.inject("doc/README.1", "\ninjected", after="--start--", pretend=True)
        self.assertEqual(read(self.dst("doc/README.1")), "--start--\nREADME\n--end--\n")

    def test_invoke_inject_existing_data(self):
        self.inject("doc/README.1", "\ninjected", after="--start--")
        self.inject("doc/README.1", "\ninjected", after="--start--")
        self.assertEqual(read(self.dst("doc/README.1")), "--start--\ninjected\nREADME\n--end--\n")

    def test_revoke_inject_after(self):
        self.inject("doc/README.2", "\ntext after", after="--start--", revoke=True)
        self.assertEqual(read(self.dst("doc/README.2")), "--start--\nREADME\ntext before\n--end--\n")

    def test_revoke_inject_old_after(self):
        self.inject("doc/README.3", "\n2", after="--start--", revoke=True)
        self.assertEqual(read(self.dst("doc/README.3")), "--start--\n1\nREADME\n3\n4\n--end--\n")

    def test_revoke_inject_before(self):
        self.inject("doc/README.2", "text before\n", before="--end--", revoke=True)
        self.assertEqual(read(self.dst("doc/README.2")), "--start--\ntext after\nREADME\n--end--\n")

    def test_revoke_inject_old_before(self):
        self.inject("doc/README.3", "3\n", before="--end--", revoke=True)
        self.assertEqual(read(self.dst("doc/README.3")), "--start--\n1\n2\nREADME\n4\n--end--\n")

    def test_revoke_inject_status(self):
        self.inject("doc/README.2", "text before\n", before="--end--", revoke=True)
        self.assert_status("update", self.dst("doc/README.2"), "*red*")

    def test_revoke_inject_nonexisting_data(self):
        self.inject("doc/README.1", "\n1", after="--start--", revoke=True)
        self.assertEqual(read(self.dst("doc/README.1")), "--start--\nREADME\n--end--\n")

    def test_revoke_inject_pretend(self):
        self.inject("doc/README.2", "\ntext after", after="--start--", revoke=True, pretend = True)
        self.assertEqual(read(self.dst("doc/README.2")), "--start--\ntext after\nREADME\ntext before\n--end--\n")

