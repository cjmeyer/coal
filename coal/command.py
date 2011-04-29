# command.py


import getopt
import inspect


try:
    _getargspec = inspect.getfullargspec
except:
    _getargspec = inspect.getargspec


class _OptHandler(object):
    def __init__(self, cmd, long_, short_, store=None):
        self._cmd = cmd
        self._long = long_
        self._short = short_
        self._argreq = False

        if store is None:
            fn = getattr(cmd, 'opt_%s' % self._long.replace('-', '_'))
            self._argreq = _getargspec(fn).args != 0
            def handler(arg):
                 fn(arg) if self._argreq else fn()

        elif isinstance(store, dict):
            self._argreq = True
            def handler(arg):
                self._cmd[self._long] = store[arg]

        elif callable(store):
            self._argreq = True
            def handler(arg):
                self._cmd[self._long] = store(arg)

        else:
            self._argreq = False
            def handler(arg):
                self._cmd[self._long] = store

        self._handler = handler

    @property
    def long_opt(self):
        return self._long

    @property
    def short_opt(self):
        return self._short or ''

    @property
    def long_getopt(self):
        return '%s%s' % (self._long, self._argreq and '=' or '')

    @property
    def short_getopt(self):
        if not self._short:
            return ''
        return '%s%s' % (self._short, self._argreq and ':' or '')

    def __call__(self, arg):
        return self._handler(arg)


class Opt(object):
    def __init__(self, long_, short_, store=None):
        self._long = long_
        self._short = short_
        self._store = store

    def build_handler(self, cmd):
        return _OptHandler(cmd, self._long, self._short, self._store)


class Command(object):
    def __init__(self, parent=None):
        self._parent = parent
        self._handlers = []
        self._options = {}
        options = getattr(self, 'opts', [])
        for opt in options:
            handler = opt.build_handler(self)
            self._handlers.append(handler)
            self._options[handler.long_opt] = None

    def __getitem__(self, key):
        return self.options.get(key, None)

    def __setitem__(self, key, value):
        self._options[key] = value

    @property
    def cmdtable(self):
        return getattr(self, 'cmds', {})

    @property
    def options(self):
        return self._options

    def findcmd(self, cmdname):
        for cmd, cls in self.cmdtable.iteritems():
            if cmdname in cmd.split('|'):
                return cls(self)

    def parse(self, args):
        args = self._parse(args)
        if args and self.cmdtable:
            self.subcmd = self.findcmd(args.pop(0))
            self.subcmd.parse(args)
            args = []
        self.parse_args(*args)

    @property
    def _merged_optlist(self):
        if self._parent:
            short_opts, long_opts = self._parent._merged_optlist
        else:
            short_opts, long_opts = {}, {}
        for opt in self._handlers:
            if opt.short_opt:
                short_opts[opt.short_opt] = opt
            long_opts[opt.long_opt] = opt
        return short_opts, long_opts

    def _parse(self, args):
        long_getopts = []
        short_getopts = []
        long_, short_ = self._merged_optlist
        for opt, handler in long_.iteritems():
            long_getopts.append(handler.long_getopt)
        for opt, handler in short_.iteritems():
            short_getopts.append(handler.short_getopt)
        long_.update(short_)
        _getopt = self.cmdtable and getopt.getopt or getopt.gnu_getopt
        opts, args = _getopt(args, ''.join(short_getopts), long_getopts)
        for opt, arg in opts:
            opt = opt[2:] if opt[1] == '-' else opt[1:]
            long_[opt](arg)
        return args

