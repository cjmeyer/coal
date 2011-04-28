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
            handler_ = getattr(cmd, "opt_%s" % self.name.replace("-", "_"))
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
    def __init__(self):
        self.options = {}
        self._short = []
        self._long = []
        self._handlers = {}
        for opt in self.opts:
            handler, takes_arg = opt.build_handler(self)
            if opt.short:
                flag = "%s%s" % (opt.short, takes_arg and ":" or "")
                self._short.append(flag)
                self._handlers["-%s" % opt.short] = handler
            flag = "%s%s" % (opt.name, takes_arg and "=" or "")
            self._long.append(flag)
            self._handlers["--%s" % opt.name] = handler
            self.options[opt.name] = None

    def parse(self, args):
        opts, args = getopt.getopt(args, "".join(self._short), self._long)
        for opt, arg in opts:
            self._handlers[opt](arg)
        self.parse_args(*args)

    def __getitem__(self, key):
        return self.options.get(key, None)

    def __setitem__(self, key, value):
        self.options[key] = value

