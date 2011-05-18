# test_fileop.py


import coal
import mock
import shutil
import stat
import StringIO
import unittest2 as unittest

from mock import patch

from coal import error, shell, path, FileOp


def make_file(p):
    mkdir(os.path.dirname(p))
    return open(p, 'w')


_conflict_msg = (
        'How do you wish to proceed with this file?\n'
        'over(w)rite, (s)kip, (r)ender, (d)iff, (a)bort: ')


class FileOpBaseHelper(unittest.TestCase):
    def build_shell(self, stdin, stdout, stderr):
        return shell.Shell(stdin, stdout, stderr)

    def build_fop(self, shell_, srcroot, dstroot):
        return FileOp(shell_, srcroot, dstroot)

    def setUp(self):
        self.basepath = path(__file__).dirname()
        self.srcroot = self.basepath / 'templates'
        self.dstroot = self.basepath / 'results'
        self._stdin = StringIO.StringIO()
        self._stdout = StringIO.StringIO()
        self._stderr = StringIO.StringIO()
        self.shell = self.build_shell(self._stdin, self._stdout, self._stderr)
        self.fop = self.build_fop(self.shell, self.srcroot, self.dstroot)
        if self.dstroot.exists():
            self.dstroot.removedirs()
        self.dstroot.makedirs(0755)

    def tearDown(self):
        if self.dstroot.exists():
            shutil.rmtree(self.dstroot, ignore_errors=True)

    def src(self, p):
        return self.srcroot / p

    def dst(self, p):
        return self.dstroot / p

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


class FileOpStatusHelper(FileOpBaseHelper):
    def setUp(self):
        FileOpBaseHelper.setUp(self)
        self.shell.status = mock.Mock()

    def assert_status(self, msg, p, color=None):
        p = path(p)
        if p.isabs():
            p = p.relpath()
        self.assertEqual(self.shell.status.call_args_list.pop(0), ((msg.rjust(12),), {'color':color}))
        self.assertEqual(self.shell.status.call_args_list.pop(0), (('  %s\n' % p,), {}))


class FileOpPathExpansionTest(FileOpBaseHelper):
    def test_expand_src_abspath(self):
        self.assertEqual(self.fop.src('/path/to/src'), self.src('/path/to/src'))

    def test_expand_src_relpath(self):
        self.assertEqual(self.fop.src('path/to/src'), self.src('path/to/src'))

    def test_expand_dst_abspath(self):
        self.assertEqual(self.fop.dst('/path/to/dst'), self.dst('/path/to/dst'))

    def test_expand_dst_relpath(self):
        self.assertEqual(self.fop.dst('path/to/dst'), self.dst('path/to/dst'))

    def test_expand_dst_simple_pattern(self):
        self.fop['foo'] = 'bar'
        self.assertEqual(self.fop.dst('path/to/%foo%.txt'), self.dst('path/to/bar.txt'))

    def test_expand_dst_complext_pattern(self):
        self.fop['foo'] = 'bar'
        self.assertEqual(self.fop.dst('path/to/%%_%%%foo%_%%.txt'), self.dst('path/to/%_%bar_%.txt'))


class FileOpStatusTest(FileOpStatusHelper):
    def test_status_plain(self):
        self.fop.status('status', 'path/to/file')
        self.assert_status('status', 'path/to/file')

    def test_status_color(self):
        self.fop.status('status', '/path/to/file', color=id(self))
        self.assert_status('status', '/path/to/file', color=id(self))


class FileOpInsideTest(FileOpStatusHelper):
    def test_inside_relative_dir(self):
        with self.fop.inside('path/to/dir'):
            self.assertEqual(self.fop.dstroot, self.dst('path/to/dir'))
        self.assertEqual(self.fop.dstroot, self.dstroot)

    def test_inside_absolute_dir(self):
        with self.fop.inside('/path/to/dir'):
            self.assertEqual(self.fop.dstroot, self.dst('/path/to/dir'))
        self.assertEqual(self.fop.dstroot, self.dstroot)


class FileOpMkdirTest(FileOpStatusHelper):
    def mkdir(self, dst, pretend=False, chmod=None):
        self.fop.pretend = pretend
        self.fop.mkdir(dst, chmod=chmod)
    
    def test_mkdir(self):
        self.mkdir('path/to/dir')
        self.assertTrue(self.dst('path/to/dir').isdir())

    def test_mkdir_pretend(self):
        self.mkdir('path/to/dir', pretend=True)
        self.assertFalse(self.dst('path/to/dir').exists())

    def test_mkdir_status_create(self):
        self.mkdir('path/to/dir')
        self.assert_status('create', self.dst('path/to/dir'), color='*green*')

    def test_mkdir_status_exists(self):
        self.dst('path/to/dir').makedirs(0755)
        self.mkdir('path/to/dir')
        self.assert_status('exist', self.dst('path/to/dir'), color='*blue*')


class FileOpMkdirTest(FileOpStatusHelper):
    def setUp(self):
        FileOpStatusHelper.setUp(self)
        self.dst('path/to/dir').makedirs(0755)

    def rmdir(self, dst, pretend=False):
        self.fop.pretend = pretend
        self.fop.rmdir(dst)

    def test_rmdir(self):
        self.rmdir('path/to/dir')
        self.assertFalse(self.dst('path/to/dir').exists())

    def test_rmdir_pretend(self):
        self.rmdir('path/to/dir', pretend=True)
        self.assertTrue(self.dst('path/to/dir').isdir())

    def test_rmdir_status_remove(self):
        self.rmdir('path/to/dir')
        self.assert_status('remove', self.dst('path/to/dir'), color='*red*')


class FileOpCopyFileTest(FileOpStatusHelper):
    def _op(self, src, dst=None, mode=None):
        self.fop.copy_file(src, dst, mode=mode)

    def op(self, src, dst=None, mode=None, pretend=False, force=False, skip=False):
        self.fop.pretend = pretend
        self.fop.force = force
        self.fop.skip = skip
        self._op(src, dst, mode=mode)

    def copy_conflict(self, fname, contents, **kw):
        self.dst(fname).write_bytes(contents)
        self.op(fname, **kw)
        
    def copy_conflict_menu(self, fname, *choices):
        self.dst(fname).write_bytes('conflict\n')
        self.stdin = '\n'.join(choices) + '\n'
        self.op(fname)
        self.assert_status('conflict', self.dst(fname), color='*red*')

    def test_copy_file(self):
        self.op('source1.txt', 'path/to/result.txt')
        self.assertEqual(self.src('source1.txt').bytes(), self.dst('path/to/result.txt').bytes())

    def test_copy_file_no_dst(self):
        self.op('source1.txt')
        self.assertEqual(self.src('source1.txt').bytes(), self.dst('source1.txt').bytes())

    def test_copy_file_chmod_same(self):
        self.op('source1.txt')
        self.assertEqual(self.src('source1.txt').stat().st_mode, self.dst('source1.txt').stat().st_mode)

    def test_copy_file_chmod_0777(self):
        self.op('source1.txt', mode=0777)
        self.assertEqual(stat.S_IMODE(self.dst('source1.txt').stat().st_mode), 0777)

    def test_copy_file_chmod_0644(self):
        self.op('source1.txt', mode=0644)
        self.assertEqual(stat.S_IMODE(self.dst('source1.txt').stat().st_mode), 0644)

    def test_copy_file_pretend(self):
        self.op('source1.txt', pretend=True)
        self.assertFalse(self.dst('source1.txt').exists())

    def test_copy_file_status_create(self):
        self.op('source1.txt')
        self.assert_status('create', self.dst('source1.txt'), color='*green*')

    def test_copy_file_status_identical(self):
        self.copy_conflict('source1.txt', 'source 1\n')
        self.assert_status('identical', self.dst('source1.txt'), color='*blue*')

    def test_copy_file_skip(self):
        self.copy_conflict('source1.txt', 'conflict', skip=True)
        self.assertEqual(self.dst('source1.txt').bytes(), 'conflict')

    def test_copy_file_skip_status(self):
        self.copy_conflict('source1.txt', 'conflict', skip=True)
        self.assert_status('skip', self.dst('source1.txt'), color='*yellow*')

    def test_copy_file_force(self):
        self.copy_conflict('source1.txt', 'conflict', force=True)
        self.assertEqual(self.dst('source1.txt').bytes(), self.src('source1.txt').bytes())

    def test_copy_file_force_status(self):
        self.copy_conflict('source1.txt', 'conflict', force=True)
        self.assert_status('force', self.dst('source1.txt'), color='*yellow*')

    def test_copy_file_conflict_overwrite(self):
        self.copy_conflict_menu('source1.txt', 'w')
        self.assertEqual(self.dst('source1.txt').bytes(), self.src('source1.txt').bytes())
        self.assertEqual(self.stdout, _conflict_msg + 'Overwritten\n')

    def test_copy_file_conflict_skip(self):
        self.copy_conflict_menu('source1.txt', 's')
        self.assertEqual(self.dst('source1.txt').bytes(), 'conflict\n')
        self.assertEqual(self.stdout, _conflict_msg + 'Skipped\n')

    def test_copy_file_conflict_abort(self):
        self.assertRaises(error.AbortError, self.copy_conflict_menu, 'source1.txt', 'a')
        self.assertEqual(self.dst('source1.txt').bytes(), 'conflict\n')

    def test_copy_file_conflict_menu(self):
        self.copy_conflict_menu('source1.txt', 'r', 'd', 'w')
        dst = self.dst('source1.txt').relpath()
        expected = ''.join([_conflict_msg, 'Rendering %s\n' % dst,
                            '\n',
                            'source 1\n',
                            '\n',
                            _conflict_msg, 'Showing differences for %s\n' % dst,
                            '\n',
                            '--- old\n',
                            '+++ new\n',
                            '@@ -1,1 +1,1 @@\n',
                            '-conflict\n',
                            '+source 1\n',
                            '\n',
                            _conflict_msg, 'Overwritten']).splitlines()
        expected = [l.rstrip() for l in expected]
        actual = [l.rstrip() for l in self.stdout.splitlines()]
        self.assertEqual(expected, actual)


class FileOpRemoveFileTest(FileOpStatusHelper):
    def remove_file(self, p, pretend=False):
        self.fop.pretend = pretend
        p = self.dst(p)
        if not p.dirname().exists():
            p.dirname().makedirs()
        p.write_bytes('source 1\n')
        self.assertTrue(p.isfile())
        self.fop.remove_file(p)

    def test_remove_file(self):
        self.remove_file('source1.txt')
        self.assertFalse(self.dst('source1.txt').exists())

    def test_remove_file_status(self):
        self.remove_file('path/to/result.txt')
        self.assert_status('remove', self.dst('path/to/result.txt'), color='*red*')

    def test_remove_file_pretend(self):
        self.remove_file('path/to/result.txt', pretend=True)
        self.assertEqual(self.dst('path/to/result.txt').bytes(), 'source 1\n')

    def test_remove_file_pretend_status(self):
        self.remove_file('path/to/result.txt', pretend=True)
        self.assert_status('remove', self.dst('path/to/result.txt'), color='*red*')

    def test_remove_file_not_present(self):
        self.fop.remove_file('source1.txt')
        self.assertEqual(self.shell.status.call_count, 0)


class FileOpTemplateTest(FileOpCopyFileTest):
    def _op(self, src, dst=None, mode=None):
        self.fop.template(src, dst, mode=mode)

    def test_render_template(self):
        self.fop['foo'] = 'bar'
        self.op('source.t', 'path/to/result.txt')
        self.assertEqual(self.dst('path/to/result.txt').bytes(), 'bar\n')


class FileOpCopyDirectoryTest(FileOpBaseHelper):
    def test_copy_directory(self):
        self.src('template_dir/dir3').makedirs_p()

        files, templates, directories = {}, {}, {}

        def copy_file(src, dst):
            files[path(dst).normpath()] = path(src).normpath()

        def template(src, dst):
            templates[path(dst).normpath()] = path(src).normpath()

        def directory(dst):
            directories[path(dst).normpath()] = None

        self.fop.copy_file = copy_file
        self.fop.template = template
        self.fop.directory = directory

        a = self.fop.copy_directory("template_dir", "test_dir", templates=["*.t"])

        def test(l, p):
            src = self.src(path('template_dir') / p)
            dst = self.dst(path('test_dir') / p)
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
        self.dst('README.1').write_bytes('--start--\nREADME\n--end--\n')

    def inject(self, p, txt, pretend=False, **kw):
        self.fop.pretend = pretend
        self.fop.inject(p, txt, **kw)

    def test_inject_after(self):
        self.inject('README.1', '\ninjected', after='--start--')
        self.assertEqual(self.dst('README.1').bytes(), '--start--\ninjected\nREADME\n--end--\n')

    def test_inject_before(self):
        self.inject('README.1', 'injected\n', before='--end--')
        self.assertEqual(self.dst('README.1').bytes(), '--start--\nREADME\ninjected\n--end--\n')

    def test_inject_status(self):
        self.inject('README.1', '\ninjected', after='--start--')
        self.assert_status('update', self.dst('README.1'), color='*green*')

    def test_inject_pretend(self):
        self.inject('README.1', '\ninjected', after='--start--', pretend=True)
        self.assertEqual(self.dst('README.1').bytes(), '--start--\nREADME\n--end--\n')

    def test_inject_pretend_status(self):
        self.inject('README.1', '\ninjected', after='--start--', pretend=True)
        self.assert_status('update', self.dst('README.1'), color='*green*')

    def test_inject_existing_data(self):
        self.inject('README.1', '\ninjected', after='--start--')
        self.inject('README.1', '\ninjected', after='--start--')
        self.assertEqual(self.dst('README.1').bytes(), '--start--\ninjected\nREADME\n--end--\n')

    def test_inject_force_existing_data(self):
        self.inject('README.1', '\ninjected', after='--start--')
        self.inject('README.1', '\ninjected', after='--start--', force=True)
        self.assertEqual(self.dst('README.1').bytes(), '--start--\ninjected\ninjected\nREADME\n--end--\n')


class FileOpEraseTest(FileOpStatusHelper):
    def setUp(self):
        FileOpStatusHelper.setUp(self)
        self.dst('README.1').write_bytes('--start--\ntext after\nREADME\ntext before\n--end--\n')
        self.dst('README.2').write_bytes('--start--\n1\n2\nREADME\n3\n4\n--end--\n')

    def erase(self, p, txt, pretend=False, **kw):
        self.fop.pretend = pretend
        self.fop.erase(p, txt, **kw)

    def test_erase_after(self):
        self.erase('README.1', '\ntext after', after='--start--')
        self.assertEqual(self.dst('README.1').bytes(), '--start--\nREADME\ntext before\n--end--\n')

    def test_erase_before(self):
        self.erase('README.1', 'text before\n', before='--end--')
        self.assertEqual(self.dst('README.1').bytes(), '--start--\ntext after\nREADME\n--end--\n')

    def test_erase_old_after(self):
        self.erase('README.2', '\n2', after='--start--')
        self.assertEqual(self.dst('README.2').bytes(), '--start--\n1\nREADME\n3\n4\n--end--\n')

    def test_erase_old_before(self):
        self.erase('README.2', '3\n', before='--end--')
        self.assertEqual(self.dst('README.2').bytes(), '--start--\n1\n2\nREADME\n4\n--end--\n')

    def test_erase_status(self):
        self.erase('README.1', 'text after', after='--start--')
        self.assert_status('update', self.dst('README.1'), color='*red*')

    def test_erase_nonexisting_data(self):
        self.erase('README.2', '\n5', after='--start--')
        self.assertEqual(self.dst('README.2').bytes(), '--start--\n1\n2\nREADME\n3\n4\n--end--\n')

    def test_erase_pretend(self):
        self.erase('README.2', '\n2', after='--start--', pretend=True)
        self.assertEqual(self.dst('README.2').bytes(), '--start--\n1\n2\nREADME\n3\n4\n--end--\n')

    def test_erase_pretend_status(self):
        self.erase('README.2', '\n2', after='--start--', pretend=True)
        self.assert_status('update', self.dst('README.2'), color='*red*')

