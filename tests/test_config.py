# test_config.py


import StringIO
import unittest2 as unittest

from coal import config, path


class ConfigStoreTest(unittest.TestCase):
    def setUp(self):
        self.cfg1 = config.ConfigStore()
        self.cfg1.set('section1', 'key1', 'value1', 'source1')

        self.cfg2 = config.ConfigStore()
        self.cfg2.set('section2', 'key2', 'value2')

    def test_set_with_source(self):
        self.assertEqual(self.cfg1.get('section1', 'key1'), 'value1')
        self.assertEqual(self.cfg1.source('section1', 'key1'), path('source1').abspath())

    def test_set_without_source(self):
        self.assertEqual(self.cfg2.get('section2', 'key2'), 'value2')
        self.assertEqual(self.cfg2.source('section2', 'key2'), None)

    def test_get_with_default(self):
        self.assertEqual(self.cfg1.get('section3', 'key3'), None)
        self.assertEqual(self.cfg1.get('section3', 'key3', 'default'), 'default')

    def test_update(self):
        self.cfg1.update(self.cfg2)

        self.assertEqual(self.cfg1.get('section1', 'key1'), 'value1')
        self.assertEqual(self.cfg1.source('section1', 'key1'), path('source1').abspath())
        self.assertEqual(self.cfg1.get('section2', 'key2'), 'value2')
        self.assertEqual(self.cfg1.source('section2', 'key2'), None)

        self.cfg2.set('section2', 'key2', 'VALUE2')

        self.assertEqual(self.cfg1.get('section2', 'key2'), 'value2')

    def test_unset(self):
        self.cfg1.unset('section1', 'key1')
        self.assertEqual(self.cfg1.get('section1', 'key1'), None)

    def test_copy(self):
        cfg3 = self.cfg1.copy()

        self.cfg1.set('section1', 'key1', 'VALUE1')
        self.assertEqual(cfg3.get('section1', 'key1'), 'value1')

    def test_get_sections(self):
        self.cfg1.update(self.cfg2)
        self.assertEqual(sorted(self.cfg1.sections()), ['section1', 'section2'])

    def test_contains_section(self):
        self.assertTrue('section1' in self.cfg1)

    def test_iter_sections(self):
        self.cfg1.update(self.cfg2)
        self.assertEqual(sorted(s for s in self.cfg1), ['section1', 'section2'])

    def test_iter_secction_items(self):
        self.cfg1.set('section1', 'key2', 'value2')
        self.assertEqual(sorted(v for v in self.cfg1.items('section1')),
                         [('key1', 'value1'), ('key2', 'value2')])


class IniConfigStore(unittest.TestCase):
    ini_file = path(__file__).parent / 'config/ini_test.conf'

    def _test(self, section, key, value, source=None):
        self.assertEqual(self.cfg.get(section, key), value)
        self.assertEqual(self.cfg.source(section, key), source or self.ini_file.abspath())

    def _test_expected(self):
        self._test('section1', 'key1', 'value1')
        self._test('section1', 'key2', 'value2')
        self._test('section2', 'key3', 'value3')
        self._test('section2', 'key4', 'value4')

    def test_load_file(self):
        self.cfg = config.IniConfigStore.load_file(self.ini_file)
        self._test_expected()

    def test_read_file(self):
        self.cfg = config.IniConfigStore()
        with open(self.ini_file, 'r') as f:
            self.cfg.read(f)
        self._test_expected()

    def test_write_file(self):
        fp = StringIO.StringIO()

        cfg = config.IniConfigStore()
        cfg.set('section1', 'key1', 'value1')
        cfg.set('section1', 'key2', 'value2')
        cfg.set('section2', 'key3', 'value3')
        cfg.set('section2', 'key4', 'value4')

        cfg.write(fp)

        fp = StringIO.StringIO(fp.getvalue())
        fp.name = '/fp'

        self.cfg = config.IniConfigStore()
        self.cfg.read(fp)
        self._test('section1', 'key1', 'value1', '/fp')
        self._test('section1', 'key2', 'value2', '/fp')
        self._test('section2', 'key3', 'value3', '/fp')
        self._test('section2', 'key4', 'value4', '/fp')


class ConfigTest(unittest.TestCase):
    ini_file = path(__file__).parent / 'config/ini_test.conf'

    def setUp(self):
        self.cfg = config.Config()
        self.cfg.read_file(self.ini_file)
        
    def test_get_config(self):
        self.assertEqual(self.cfg.config('section1', 'key1'), 'value1')

    def test_get_config_source(self):
        self.assertEqual(self.cfg.source('section1', 'key1'), self.ini_file.abspath())

    def test_get_config_path(self):
        self.assertEqual(self.cfg.configpath('section1', 'key2'), self.ini_file.abspath() / 'value2')

    def test_set_config_with_source(self):
        self.cfg.setconfig('section3', 'key5', 'value5', '/source5')
        self.assertEqual(self.cfg.config('section3', 'key5'), 'value5')
        self.assertEqual(self.cfg.source('section3', 'key5'), '/source5')

    def test_set_config_without_source(self):
        self.cfg.setconfig('section3', 'key5', 'value5')
        self.assertEqual(self.cfg.config('section3', 'key5'), 'value5')
        self.assertEqual(self.cfg.source('section3', 'key5'), None)

    def test_unset_config(self):
        self.cfg.unsetconfig('section1', 'key1')
        self.assertEqual(self.cfg.config('section1', 'key1'), None)
        self.assertEqual(self.cfg.source('section1', 'key1'), None)

    def test_copy_config(self):
        cfg = self.cfg.copy()

        self.cfg.setconfig('section1', 'key1', 'VALUE1')
        self.assertEqual(cfg.config('section1', 'key1'), 'value1')

