# cmdparse.py


import error
import getopt


class opt(object):
    def __init__(self, short_opt, long_opt, action, type_):
        self.short_opt, self.long_opt, self.action_, self.type_ = (
            short_opt, long_opt, action, type_)
    def build_action(self):
        return self.action_(self)


def store_const(opt_):
    """ Store a constant value in the option dictionary. """
    def action(arg, parsed_opts):
        parsed_opts[opt_.long_opt] = opt_.type_
    return action, False

def _store(opt_, arg):
    """
    Parse a value to be stored/appended to the option dictionary.

    A value to be parsed from an option argument can be parsed in one of two
    ways. If the option specifies a dictionary as the option 'type', then the
    argument string is used to lookup the value to be returned. This allowes the
    implementation of enumerated option arguments. If this lookup failes then
    the option 'type' is called with the option argument as the parameter. This
    allowes internal types and functions such as ``int`` or ``float`` or ``str``
    to be used.
    """
    try:
        return opt_.type_[arg]
    except TypeError:
        return opt_.type_(arg)

def store(opt_):
    """ Store a parsed value in the option dictionary. """
    def action(arg, parsed_opts):
        parsed_opts[opt_.long_opt] = _store(opt_, arg)
    return action, True

def append(opt_):
    """ Append a parsed value to the option dictionary element. """
    def action(arg, parsed_opts):
        arg = _store(opt_, arg)
        try:
            parsed_opts[opt_.long_opt].append(arg)
        except KeyError, AttributeError:
            parsed_opts[opt_.long_opt] = [arg]
    return action, True


class _CmdOptError(Exception):
    pass


def _parse(args, opts, parsed_opts, gnu=False):
    """
    Parses a list of command line options.

    The parsed positional arguments are returned as a list of strings. The
    keyword arguments are parsed and used to update the provided ``parsed_opts``
    dictionary. How the dictionary is updated is based on the action associated
    with the option being parsed. The valid options are specified in a list of
    ``opt`` instances and is of the form::

        opts = [
            opt("a", "alpha", store, int, ...),
            opt("b", "bravo", store, float, ...),
            opt("", "charlie", store_const, True, ...),
            opt("", "delta", append, int, ...),
            opt("e", "echo", store, {"a":1,...}, ...)
        ]

    Note that all options require a long version which is used as the key into
    the parsed opts dictionary.

    :Parameters:
      - `args`: List of command line options to parse
      - `opts`: List of valid command line options
      - `parsed_opts`: Dictionary to store parsed options into
      - `gnu`: Parse GNU style ``getopt`` options
    """
    short_opts = []
    long_opts = []
    opt_actions = {}
    for opt in opts:
        action, takes_arg = opt.build_action()
        opt_actions["--%s" % opt.long_opt] = action
        long_opt = takes_arg and "%s=" % opt.long_opt or opt.long_opt
        long_opts.append(long_opt)
        if opt.short_opt:
            opt_actions["-%s" % opt.short_opt] = action
            short_opt = takes_arg and "%s:" % opt.short_opt or opt.short_opt
            short_opts.append(short_opt)
    getopt_ = gnu and getopt.gnu_getopt or getopt.getopt
    try:
        opts, args = getopt_(args, "".join(short_opts), long_opts)
    except getopt.GetoptError as e:
        raise _CmdOptError(e)
    for opt, arg in opts:
        try:
            opt_actions[opt](arg, parsed_opts)
        except (ValueError, KeyError) as e:
            raise _CmdOptError("invalid option argument: %s" % arg)
    return args


def _findcmd(cmd, cmdtable):
    for aliases, entry in cmdtable.iteritems():
        if cmd in aliases.split("|"):
            return entry


class _cmd(object):
    def __init__(self, fn, args, opts):
        self.fn, self.args, self.opts = fn, args, opts
    def __call__(self):
        return self.fn(*self.args, **self.opts)


def parse(opts_, cmdtable, args=None):
    """
    Parses a list of command line options and sub-commands.

    If a command table, ``cmdtable``, is not empty, then it is assumed that the
    first positional argument should be a command name. If the command is found
    in the command table, options after the command are assumed to be both
    global and command specific options. If the command is not found, a
    ``CmdParseError`` exception will be raised.

    In the case where the command specifies an option whose long name conflicts
    with an option long name in the global options, it will be treated as a
    global option if it is before the command, or as a command option if it is
    after the command.

    The command table is specified as follows::

        cmdtable = {
            "cmd1|command1":
                (cmd1_function,
                 [opt(...),
                  opt(...),
                  opt(...)]
                 "usage string")
        }

    Note that command aliases are combined with a ''|'' character.

    :Parameters:
      - `opts_`: List of global options (options not specific to the command).
      - `cmdtable`: Table os valid sub-commands.
      - `args`: The command line arguments to parse. If not provided, the system
           argumens ``sys.argv[1:]`` are used.
    """
    if args is None:
        args = sys.argv[1:]
    name = None
    opts = {}
    try:
        args = _parse(args, opts_, opts)
        if args and cmdtable:
            name = args.pop(0)
            entry = _findcmd(name, cmdtable)
            if not entry:
                raise error.CmdParseError(name)
            cmdopts_ = list(entry[1])
            cmdkeys_ = [opt.long_opt for opt in cmdopts_]
            globals_ = []
            cmdopts = {}
            for opt in opts_:
                if opt.long_opt not in cmdkeys_:
                    cmdopts_.append(opt)
                    globals_.append(opt.long_opt)
                    if opt.long_opt in opts:
                        cmdopts[opt.long_opt] = opts[opt.long_opt]
            cmdargs = _parse(args, cmdopts_, cmdopts)
            for key in globals_:
                if key in cmdopts:
                    opts[key] = cmdopts.pop(key)
            args = [_cmd(entry[0], cmdargs, cmdopts)] + args
    except _CmdOptError as e:
        raise error.CmdParseError(name, str(e))
    return args, opts

