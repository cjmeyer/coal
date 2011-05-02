# options.py


import coal
import getopt
import inspect
import sys
import util

from error import SignatureError, OptionsError


try:
    _getargspec = inspect.getfullargspec
except:
    _getargspec = inspect.getargspec


class Opt(object):
    """
    Represents a command line option or flag and the associated action.

    A list of ``Opt`` objects is used to represent the valid options and flags
    that are accepted by a ``Options`` object. These ``Opt`` objects are not
    part of a ``Options`` object but rather part of the class. The ``Opt``
    instances are used as factories to build the option handlers that are
    associated with a ``Options`` instance.

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

    It is possible to specify a command method to use to handle options. This is
    done by specifying the ``handler`` keyword option::

        # Simple option handled by the 'delta_handler' command method
        Opt('dela', 'd', handler='delta_handler')

    In the above example, the method 'delta_handler' of the associated
    ``Options`` instance will be used to process the provided option. If the
    method doesn't take any arguments (other than the standard ``self``
    argument), then the option will be treated as a flag, otherwise the option
    will require an argument which will be passed to the handler as a string.
    """
    def __init__(self, *args, **kw):
        self._args = args
        self._kw = kw

    def build_handler(self, cmd):
        return _OptHandler(cmd, *self._args, **self._kw)


class _OptHandler(object):
    def __init__(self, cmd, long_, short_, help=None, store=None, handler=None,
                 tag=None, metavar=None):
        """
        Internal class used to associate a option action with a particular
        ``Options`` instance.
        """
        if store and handler:
            raise OptError('cannot specify \'store\' and \'handler\'')

        self._cmd = cmd
        self._long = long_
        self._short = short_
        self._help = help or '[no help text available]'
        self._tag = tag or ''
        self._metavar = metavar or 'VALUE'
        self._argreq = False

        if store is None:
            # Use a command method to handling the option/flag.
            fn = getattr(cmd, handler)
            self._argreq = _getargspec(fn).args != 0
            def handler(arg):
                 fn(arg) if self._argreq else fn()

        elif isinstance(store, dict):
            # Enumerated option.
            self._argreq = True
            def handler(arg):
                try:
                    self._cmd[self._long] = store[arg]
                except KeyError as e:
                    raise ValueError(str(e))

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

    @property
    def help(self):
        """ Tuple of flag help name and flag description """
        flag = ' %3s%s%s%s ' % (self._short and '-%s ' % self._short,
                                self._long and '--%s ' % self._long,
                                self._argreq and '%s ' % self._metavar or '',
                                self._tag and '%s ' % self._tag)
        return flag, self._help

    def __call__(self, arg):
        """ Parse the provided option argument string """
        return self._handler(arg)


class Options(object):
    """
    Base class for command line and sub-command parsing.

    The ``Options`` class may be used to create sub-command based command line
    applications ala ``svn`` and ``git``. A ``Options`` class represents a list
    of valid command line options and a set of possible sub-commands. If the
    command provides a sub-command table/list, then the command cannot take any
    positional arguments as the first positional argument found is assumed to be
    the sub-command to invoke.

    A sub-``Options`` is able to parse the options that it defines and all the
    options provided by any of it's parent commands. A sub-command may provide
    options which override the parent command options and flags. In this case if
    a particular option or flag is before the sub-command in question, it is
    interpreted according to the parent command. If it appears after the
    sub-command it is interpreted according to the sub-command.

    Example of a ``Options`` class and sub-commands::

        class BaseOptions(Options):
            opts = [
                Opt('help', 'h', store=True) ]

        class SubOptions1(BaseOptions):
            opts = [
                Opt('alpha', 'a', store=True),
                Opt('bravo', 'b', store=int) ]

        class SubOptions2(BaseOptions):
            opts = [
                Opt('alpha', 'a', store=str),
                Opt('charlie', 'c', store={'a':1, 'b':2, 'c':3}) ]

            def parse_args(self, *args):
                # ...process the list of positional arguments...

        class MyOptions(Options):
            usage = 'Usage string for Mycommand'
            cmds = {
                'cmd1|command1':SubOptions1,
                'cmd2|command2':SubOptions2 }

            opts = [
                Opt('alpha, 'a', store=int),
                Opt('delta, 'd') ]

            def opt_delta(self, arg):
                # ...process 'delta' argument 'arg'...

    Objects can also inherit from sub-classes of ``Options`` and in so doing
    inherit their available options. In the above example both ``SubOptions1``
    and ``SubOptions2`` inherit from ``BaseOptions`` and therefore accept the
    ``--help`` or ``-h`` options.

    After the command line options are parsed, any left over positional
    arguments are processed by calling the ``parsed_args`` method of the last
    sub-command. It is guaranteed that all previous options and flags have
    already been processed. The positional arguments will be passed to
    ``parsed_args`` in expanded form, not as a list, so the signature of the
    ``parsed_args`` method can be used to determine if the correct number of
    positional arguments as provided. The ``pared_args`` method will be called
    even if there are no positional arguments.

    ''desc''
        The description of the option set/command. The non-whitespace character
        up to the first newline character is assumed to be the short
        description. The rest is considered to be the long description and is
        formated assuming to be ReST source text.

    ''usage''
        The short usage string for the command. This is the usage string printed
        out as part of the command help.

    ''opts''
        List of ``Opt`` instances used to specify the valid options recognized
        by the command. This class parameter *MUST* be defined for option
        inheritance to properly work.

    ''cmds''
        Dictionary mapping sub-command names with their associated ``Options``
        sub-classes. Each command name (key to the dictionary) is a list of
        aliases separated by the ''|'' character.
    """

    desc = '[no help text available]'

    def __init__(self, parent=None, ui=None, name=None, aliases=None):
        self.subcmd = None
        self.ui = ui or coal.Shell()
        self._parent = parent
        self._cmdname = name
        self._cmdaliases = aliases or []
        self._handlers = []
        self._options = {}

        options = util.accumulate_class_list(self.__class__, 'opts')
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
        """ The ``Options`` object's table of sub-commands """
        return getattr(self, 'cmds', {})

    @property
    def options(self):
        """ The list of build option handlers """
        return self._options

    @classmethod
    def short_desc(cls):
        return cls.desc.lstrip().split('\n', 1)[0]

    @classmethod
    def long_desc(cls):
        try:
            return cls.desc.lstrip().split('\n', 1)[1]
        except:
            return ''

    def findcmd(self, cmdname):
        """
        Create a ``Options`` object for the specified sub-command.

        If the specified sub-command is not found, then ``None`` is returned.
        The ``Options`` object's sub-command table is searched for the
        associated command class. Each entry in the command table dictionary
        is a key with a list of aliases separated by ''|'' characters and the
        command class used to parse options.
        """
        for cmd, cls in self.cmdtable.iteritems():
            aliases = cmd.split('|')
            if cmdname in aliases:
                return cls(self, ui=self.ui, name=cmdname, aliases=aliases)

    def parse(self, args=None):
        """
        Parse a list of command line options.

        Parses the list of command line options against the options/flags and
        sub-commands of this ``Options`` sub-class. If no options are provided,
        then the system list ``sys.argv[1:]`` is used.

        Will call ``parse_args`` with any un-parsed positional arguments.

        Raises a ``OptionsError`` exception if the specified sub-command is not
        found or if the wrong number of positional arguments are specified to
        the final (sub-)command.
        """
        if args is None:
            args = sys.argv[1:]
        args = self._parse(args)
        if args and self.cmdtable:
            cmdname = args.pop(0)
            self.subcmd = self.findcmd(cmdname)
            if self.subcmd is None:
                raise OptionsError('unknown command: %s' % cmdname)
            self.subcmd.parse(args)
        else:
            try:
                util.checksignature(self.parse_args, *args)
            except SignatureError as e:
                raise OptionsError('wrong number of arguments')
        if not self._parent:
            self._post_options()

    def post_options(self):
        """ Default post option parsing hook. """

    def parse_args(self):
        """ Default positional argument parser; don't accept arguments. """

    def help(self):
        """
        Write option help out to the provide ui/shell.

        The help output consists of a usage string, a short command description,
        a detailed/long command description (formated from ReST - ReStructured
        Text), optional list of valid sub-commands, and a list of option groups
        (each option group represents the options of this or parent commands).

        Example::

            usage: app cmd [options]

            an example short description

                A longer description of the sub-command 'cmd' handled by the
                base application 'app'.

            commands:

                sub-cmd      a short description of the sub-cmd

            cmd options:

             -a --alpha      description of the 'alpha' option
             -b --bravo INT  description of the 'bravo' option

            app options:

             -c --charlie    description of the 'charlie' option

        The above example shows the help generated for a command 'cmd' handled
        by the base command (or application) 'app'. The command 'cmd' also has a
        sub-command named 'sub-cmd'.
        """
        self.ui.write('usage: %s %s\n\n' % (self._parent_usage(), self.usage))
        self.ui.write('%s\n\n' % self.short_desc())
        long_desc = self.long_desc()
        if long_desc:
            long_desc = self.ui.rst(long_desc, indent='    ')
            if long_desc:
                self.ui.write('%s\n\n' % long_desc)

        cmds = {}
        for name, cmd in self.cmdtable.iteritems():
            name = '    %s  ' % name.split('|')[0]
            cmds[name] = cmd.short_desc()

        cmds = [(key, cmds[key]) for key in sorted(cmds.iterkeys())]
        groups = []
        indent = 0

        if cmds:
            groups.append(('commands', cmds))
            indent = max(len(c[0]) for c in cmds)

        indent_, groups_ = self._option_help()

        groups.extend(groups_)
        indent = max(indent, indent_)
        hanging = indent * ' '
        for group in groups:
            self.ui.write('%s:\n\n' % group[0])
            for opt in group[1]:
                self.ui.write('%s\n' % util.wrap(
                    opt[1], self.ui.termwidth(), opt[0].ljust(indent), hanging))
            self.ui.write('\n')

    def _option_help(self):
        """
        Group all options from this command and parent commands.

        Each set of groups is placed in a tuple of the group title (the command
        name) and a list option help tuples where each help tuple is the option
        flag entry and the option help text.
        """
        opts = [h.help for h in self._handlers]
        if opts:
            groups = [('%s options' % self._cmdname, opts)]
            width = max(len(o[0]) for o in opts)
        else:
            groups = []
            width = 0

        if self._parent:
            width_, groups_ = self._parent._option_help()
            width = max(width, width_)
            groups.extend(groups_)

        return width, groups

    def _post_options(self):
        """
        Dispatch the ''post_options'' hook.

        This method is called to execute the ''post_options'' hook. The hook of
        this ``Options`` instance is called first. If this command contains a
        sub-command, the hook dispatcher of the handler will be called next.
        """
        self.post_options()
        if self.subcmd:
            self.subcmd._post_options()

    def _parent_usage(self):
        """ Return the command sequence to this command. """
        if self._parent:
            return '%s %s' % (self._parent._parent_usage(), self._cmdname)
        return self._cmdname

    @property
    def _merged_optlist(self):
        """
        Builds complete list of short and long options.

        When parsing the command line, a sub-command must be able to parse the
        options belonging to it and any parent (sub)commands. To do this, the
        options of this ``Options`` and its parent must be merged together into
        a single set of long and short options.

        Any options flags in this sub-command that are also defined by the
        parent ``Options`` object (and it's parent...) are overridden by this
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
        """
        Parses command line arguments using ``getopt``.

        Builds the ``getopt`` style short option string and long option list and
        uses ``getopt` to parse the provided command line options. The
        ``getopt`` short and long option configurations are built from the
        merged option list for this ``Options`` instance. The corresponding
        option handlers are then executed based on the specified options.

        A ``OptionsError`` will be raised in the event of an error parsing
        either an invalid option or flag, or failing to parse an invalid option
        argument.
        """
        long_getopts = []
        short_getopts = []

        # Build the getopt short and long option string and list.
        short_, long_ = self._merged_optlist
        for opt, handler in long_.iteritems():
            long_getopts.append(handler.long_getopt)
        for opt, handler in short_.iteritems():
            short_getopts.append(handler.short_getopt)
            
        # Build the option-to-handler map.
        long_.update(short_)

        try:
            # Parse the command line argumenst.
            _getopt = self.cmdtable and getopt.getopt or getopt.gnu_getopt
            opts, args = _getopt(args, ''.join(short_getopts), long_getopts)
        except getopt.GetoptError as e:
            raise OptionsError(str(e))

        # Run option actions.
        for opt, arg in opts:
            key = opt[2:] if opt[1] == '-' else opt[1:]
            try:
                long_[key](arg)
            except ValueError as e:
                raise OptionsError(
                    'invalid argument to option %s: %s' % (opt, arg))

        return args

