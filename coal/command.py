# command.py


import getopt
import inspect
import sys


try:
    _getargspec = inspect.getfullargspec
except:
    _getargspec = inspect.getargspec


class Opt(object):
    """
    Represents a command line option or flag and the associated action.

    A list of ``Opt`` objects is used to represent the valid options and flags
    that are accepted by a ``Command`` object. These ``Opt`` objects are not
    part of a ``Command`` object but rather part of the class. The ``Opt``
    instances are used as factories to build the option handlers that are
    associated with a ``Command`` instance.

    Examples of valid options::

        # Simple flag '-a/--alpha' that stores True
        Opt('alpha', 'a', store=True)

        # Simple option '-b/--bravo' that takes an integer
        Opt('bravo', 'b', store=int)

        # Simple enumerated option '-c/--charlie'
        Opt('charlie', 'c', store={'a':1, 'b':2, 'c':3})

    Each specified option must specify a long option variant; the long option
    specifies the name of the option that will be used to store the associated
    argument of constant value. Each specified option may specify a short option
    name or an empty short option name.

    If the ``store`` keyword argument is not specified, the a method on the
    ``Command`` instance used when building the handler will be used to parse or
    handle the option. The method used is the long option name with all ''-''
    characters replaced with ''_'' and prefixed with ``opt_``: for example, an
    option ``fox-trot`` will be parsed with the option method ``opt_fox_trot``.
    """
    def __init__(self, long_, short_, store=None):
        self._long = long_
        self._short = short_
        self._store = store

    def build_handler(self, cmd):
        return _OptHandler(cmd, self._long, self._short, self._store)


class _OptHandler(object):
    def __init__(self, cmd, long_, short_, store=None):
        """
        Internal class used to associate a option action with a particular
        ``Command`` instance.
        """
        self._cmd = cmd
        self._long = long_
        self._short = short_
        self._argreq = False

        if store is None:
            # Use a command method to handling the option/flag.
            fn = getattr(cmd, 'opt_%s' % self._long.replace('-', '_'))
            self._argreq = _getargspec(fn).args != 0
            def handler(arg):
                 fn(arg) if self._argreq else fn()

        elif isinstance(store, dict):
            # Enumerated option.
            self._argreq = True
            def handler(arg):
                self._cmd[self._long] = store[arg]

        elif callable(store):
            # Option with a coercion function.
            self._argreq = True
            def handler(arg):
                self._cmd[self._long] = store(arg)

        else:
            # Simple flag (no option argument).
            self._argreq = False
            def handler(arg):
                self._cmd[self._long] = store

        self._handler = handler

    @property
    def long_opt(self):
        """ Simple long option name """
        return self._long

    @property
    def short_opt(self):
        """ Simple short option name """
        return self._short or ''

    @property
    def long_getopt(self):
        """ Long option getopt parse string """
        return '%s%s' % (self._long, self._argreq and '=' or '')

    @property
    def short_getopt(self):
        """ Short option getopt parse string """
        if not self._short:
            return ''
        return '%s%s' % (self._short, self._argreq and ':' or '')

    def __call__(self, arg):
        """ Parse the provided option argument string """
        return self._handler(arg)


class Command(object):
    """
    Base class for command line and sub-command parsing.

    The ``Command`` class may be used to create sub-command based command line
    applications ala ``svn`` and ``git``. A ``Command`` class represents a list
    of valid command line options and a set of possible sub-commands. If the
    command provides a sub-command table/list, then the command cannot take any
    positional arguments as the first positional argument found is assumed to be
    the sub-command to invoke.

    A sub-``Command`` is able to parse the options that it defines and all the
    options provided by any of it's parent commands. A sub-command may provide
    options which override the parent command options and flags. In this case if
    a particular option or flag is before the sub-command in question, it is
    interpreted according to the parent command. If it appears after the
    sub-command it is interpreted according to the sub-command.

    Example of a ``Command`` class and sub-commands::

        class SubCommand1(Command):
            opts = [
                Opt('alpha', 'a', store=True),
                Opt('bravo', 'b', store=int) ]

        class SubCommand2(Command):
            opts = [
                Opt('alpha', 'a', store=str),
                Opt('charlie', 'c', store={'a':1, 'b':2, 'c':3}) ]

            def parse_args(self, *args):
                # ...process the list of positional arguments...

        class MyCommand(Command):
            usage = 'Usage string for Mycommand'
            cmds = {
                'cmd1|command1':SubCommand1,
                'cmd2|command2':SubCommand2 }

            opts = [
                Opt('alpha, 'a', store=int),
                Opt('delta, 'd') ]

            def opt_delta(self, arg):
                # ...process 'delta' argument 'arg'...

    After hte command line options are parsed, any left over positional
    arguments are processed by calling the ``parsed_args`` method of the last
    sub-command. It is guaranteed that all previous options and flags have
    already been processed. The positional arguments will be passed to
    ``parsed_args`` in expanded form, not as a list, so the signature of the
    ``parsed_args`` method can be used to determine if the correct number of
    positional arguments as provided.

    ''opts''
        List of ``Opt`` instances used to specify the valid options recognized
        by the command. If this field is not specified, the command does not
        accept options, only positional arguments (or sub-commands)

    ''cmds''
        Dictionary mapping sub-command names with their associated ``Command``
        sub-classes. Each command name (key to the dictionary) is a list of
        aliases separated by the ''|'' character.

    ''usage''
        The short usage string for the command. This is the usage string printed
        out as part of the command help.
    """
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
        """ Get an options value """
        return self._options.get(key, None)

    def __setitem__(self, key, value):
        """ Set an options value """
        self._options[key] = value

    @property
    def cmdtable(self):
        """ The ``Command`` object's table of sub-commands """
        return getattr(self, 'cmds', {})

    @property
    def options(self):
        """ The list of build option handlers """
        return self._options

    def findcmd(self, cmdname):
        """
        Create a ``Command`` object for the specified sub-command.

        If the specified sub-command is not found, then ``None`` is returned.
        The ``Command`` object's sub-command table is searched for the
        associated command class. Each entry in the command table dictionary
        is a key with a list of aliases separated by ''|'' characters and the
        command class used to parse options.
        """
        for cmd, cls in self.cmdtable.iteritems():
            if cmdname in cmd.split('|'):
                return cls(self)

    def parse(self, args=None):
        """
        Parse a list of command line options.

        Parses the list of command line options against the options/flags and
        sub-commands of this ``Command`` sub-class. If no options are provided,
        then the system list ``sys.argv[1:]`` is used.

        Will call ``parse_args`` with any un-parsed positional arguments.
        """
        if args is None:
            args = sys.argv[1:]
        args = self._parse(args)
        if args:
            if self.cmdtable:
                self.subcmd = self.findcmd(args.pop(0))
                self.subcmd.parse(args)
            else:
                self.parse_args(*args)

    @property
    def _merged_optlist(self):
        """
        Builds complete list of short and long options.

        When parsing the command line, a sub-command must be able to parse the
        options belonging to it and any parent (sub)commands. To do this, the
        options of this ``Command`` and its parent must be merged together into
        a single set of long and short options.

        Any options flags in this sub-command that are also defined by the
        parent ``Command`` object (and it's parent...) are overridden by this
        sub-command.
        """
        if self._parent:
            # Start with the parents short and long options.
            short_opts, long_opts = self._parent._merged_optlist
        else:
            short_opts, long_opts = {}, {}

        # Override any existing options with the sub-command versions.
        for opt in self._handlers:
            if opt.short_opt:
                short_opts[opt.short_opt] = opt
            long_opts[opt.long_opt] = opt

        return short_opts, long_opts

    def _parse(self, args):
        long_getopts = []
        short_getopts = []

        long_, short_ = self._merged_optlist

        # Build the getopt long options list.
        for opt, handler in long_.iteritems():
            long_getopts.append(handler.long_getopt)

        # Build the getopt short option string.
        for opt, handler in short_.iteritems():
            short_getopts.append(handler.short_getopt)

        # Build the option-to-handler map.
        long_.update(short_)

        # Parse the command line and run the option actions.
        _getopt = self.cmdtable and getopt.getopt or getopt.gnu_getopt
        opts, args = _getopt(args, ''.join(short_getopts), long_getopts)
        for opt, arg in opts:
            opt = opt[2:] if opt[1] == '-' else opt[1:]
            long_[opt](arg)

        return args

