# command.py


import getopt
import inspect


try:
    _getargspec = inspect.getfullargspec
except:
    _getargspec = inspect.getargspec


class opt(object):
    def __init__(self, name, short, store=None):
        self.name = name
        self.short = short
        self.store = store

    def build_handler(self, cmd):
        """
        Build an option argument handler function.

        This builds a function that is able to parse an option argument and
        update the command instance appropriately. If the option stores a
        constant, then the provided handler will not take an argument. If the
        option stores a value or uses a command option method, the handler will
        accept a single string argument.

        :Parameters:
          - `cmd`: The ``Command`` object to update
        """
        if self.store is None:
            handler_ = getattr(cmd, 'opt_%s' % self.name.replace('-', '_'))
            takes_arg = _getargspec(handler_).args != 0
            if takes_arg:
                def handler(arg):
                    handler_(arg)
            else:
                def handler(arg):
                    handler_()

        elif isinstance(self.store, dict):
            takes_arg = True
            def handler(arg):
                cmd[self.name] = self.store[arg]

        elif callable(self.store):
            takes_arg = True
            def handler(arg):
                cmd[self.name] = self.store(arg)

        else:
            takes_arg = False
            def handler(arg):
                cmd[self.name] = self.store

        return handler, takes_arg


class Command(object):
    def __init__(self, parent=None):
        self.parent = parent
        self.options = {}
        self._short = []
        self._long = []
        self._handlers = {}
        for long_, short_, takes_arg, handler in self._options():
            flag = '%s%s' % (long_, takes_arg and '=' or '')
            self._long.append(flag)
            self._handlers['--%s' % long_] = handler
            if short_:
                flag = '%s%s' % (short_, takes_arg and ':' or '')
                self._short.append(flag)
                self._handlers['-%s' % short_] = handler
            self.options[long_] = None

    def _options(self):
        short_cache = {}
        long_cache = {}
        opts = []
        for opt in self.opts:
            handler, takes_arg = opt.build_handler(self)
            long_cache[opt.name] = True
            if opt.short:
                short_cache[opt.short] = True
            opts.append((opt.name, opt.short, takes_arg, handler))
        if self.parent:
            for opt in self.parent._options():
                if opt[0] not in long_cache:
                    long_cache[opt[0]] = True
                    long_ = opt[0]
                    if opt[1] not in short_cache:
                        short_cache[opt[1]] = True
                        short_ = opt[1]
                    else:
                        short_ = ''
                    opts.append((long_, short_, opt[2], opt[3]))
        return opts

    @property
    def _cmdtable(self):
        return getattr(self, 'cmds', {})

    def _findcmd(self, cmdname):
        for cmd, cls in self._cmdtable.iteritems():
            if cmdname in cmd.split('|'):
                return cls(self)

    def parse(self, args):
        opts, args = getopt.getopt(args, ''.join(self._short), self._long)
        for opt, arg in opts:
            self._handlers[opt](arg)
        if args and self._cmdtable:
            self.subcmd = self._findcmd(args.pop(0))
            self.subcmd.parse(args)
            args = []
        self.parse_args(*args)

    def __getitem__(self, key):
        return self.options.get(key, None)

    def __setitem__(self, key, value):
        self.options[key] = value

