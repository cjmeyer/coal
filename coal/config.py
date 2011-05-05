# config.py


from path import path


try:
    from configparser import RawConfigParser
except ImportError as e:
    from ConfigParser import RawConfigParser


class ConfigStore(object):
    """
    A data store for configuration data.

    Configuration data is stored in sections as key/value pairs (essentially a
    two layer dictionary). This maps well to most configuration types.
    Additional hierarchy can be imposed through section or key naming. The
    ``ConfigStore`` class provides the basic functionaliry to organize
    configuration data, copy, access, iterate and test.

    Each piece of configuration data may also have an associated source string
    which represents where the configuration value was read from or set by. This
    is particularly important when a configuration field reprsents things such
    as paths as the source may be used to interpret the value as a relative
    path.
    """
    def __init__(self, src=None):
        self._data = {}
        self._source = {}
        if src:
            self._source = src._source.copy()
            for section in src._data:
                self._data[section] = src._data[section].copy()

    def __contains__(self, section):
        return section in self._data

    def __iter__(self):
        for section in self._data:
            yield section

    def copy(self):
        """ Create a shallow copy of the configuration data. """
        return self.__class__(self)

    def get(self, section, key, default=None):
        """ Retrieve a configuration value as a string. """
        return self._data.get(section, {}).get(key, default)

    def source(self, section, key):
        """ Get the source identifier of a configuration value. """
        return self._source.get((section, key), None)

    def set(self, section, key, value, source=None):
        """ Add a configuration field to the data store. """
        source = source and path(source).abspath() or None
        if section not in self._data:
            self._data[section] = {}
        self._data[section][key] = value
        self._source[(section, key)] = source

    def unset(self, section, key):
        """ Remove a configuration field from the data store. """
        data = self._data.get(section, {})
        if key in data:
            del self._data[section][key]
        if (section, key) in self._source:
            del self._source[(section, key)]

    def update(self, src):
        """ Update this data store with the data form another. """
        for section in src._data:
            if section not in self._data:
                self._data[section] = {}
            self._data[section].update(src._data[section])
        self._source.update(src._source)

    def sections(self):
        return self._data.keys()

    def items(self, section):
        for key, value in self._data.get(section, {}).iteritems():
            yield key, value


class FileConfigStore(ConfigStore):
    """
    File based configuration store.

    The ``FileConfigStore`` class provides a class method that can be used to
    create a new configuration data store from a file on disk. The
    ``FileConfigStore`` should not be instantiated directly; it should only be
    used as a base class for other file based configuration data stores.

    Children of ``FileConfigStore`` must implement the ``read`` method which
    takes a file object to read from.
    """
    @classmethod
    def load_file(cls, fname):
        config = cls()
        with open(fname, 'r') as f:
            config.read(f)
        return config


class IniConfigStore(FileConfigStore):
    """
    INI style file based configuration data store.

    Represents configuration data that has been read from an INI file or may be
    stored to an INI file. The ``IniConfigStore`` class may be directly
    instantiated.
    """
    def __init__(self, src=None):
        ConfigStore.__init__(self, src)

    def read(self, fp):
        parser = RawConfigParser()
        parser.readfp(fp)
        for section in parser.sections():
            for key, value in parser.items(section):
                self.set(section, key, value, path(fp.name).abspath())

    def write(self, fp):
        parser = RawConfigParser()
        for section in self:
            parser.add_section(section)
            for key, value in self.items(section):
                parser.set(section, key, value)
        parser.write(fp)


class Config(object):
    """
    Basic configuration access class.

    The ``Config`` class wraps a configuration data store to provide additional
    access functions to read the configuration data back in a more useful form.
    This is particularly true for configuration fields that contain paths.
    Additionally, file read and write methods are provided.
    """
    def __init__(self, store=None):
        self._store = store or IniConfigStore()

    def copy(self):
        return self.__class__(self._store.copy())

    def config(self, section, item, default=None):
        """ Get a configuration value as a string. """
        return self._store.get(section, item, default)

    def configpath(self, section, item, default=None):
        """ Get a configuration value as a relative path to the source. """
        p = path(self._store.get(section, item))
        if not p:
            return default
        src = self.source(section, item)
        if not src:
            return default
        return path(src) / p.expanduser()

    def source(self, section, item):
        """ Get the source that set a configuration value. """
        return self._store.source(section, item)

    def setconfig(self, section, item, value, source=None):
        """ Add or update a configuration value. """
        self._store.set(section, item, value, source=source)

    def updateconfig(self, cfg):
        """ Update configuration from another ``Config`` instance. """
        self._store.update(cfg._store)

    def unsetconfig(self, section, item):
        """ Remove a configuration value from the store. """
        self._store.unset(section, item)

    def read_file(self, fname):
        with open(fname, 'r') as f:
            self._store.read(f)

    def write_file(self, fname):
        with open(fname, 'w') as f:
            self._store.write(f)

