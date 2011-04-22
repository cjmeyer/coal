# cmdparse.py


import error
import getopt


class store_const(object):
    def __init__(self, value):
        self.value = value
    def short_opt(self, name):
        return "%s" % name
    def long_opt(self, name):
        return "%s" % name
    def __call__(self, name, arg, parsed_opts):
        parsed_opts[name] = self.value


class store(object):
    def __init__(self, type_):
        self.type_ = type_
    def short_opt(self, name):
        return "%s:" % name
    def long_opt(self, name):
        return "%s=" % name
    def __call__(self, name, arg, parsed_opts):
        parsed_opts[name] = self.type_(arg)


class append(store):
    def __call__(self, name, arg, parsed_opts):
        try:
            parsed_opts[name].append(self.type_(arg))
        except:
            parsed_opts[name] = [self.type_(arg)]


def _parse(args, opts, parsed_opts, gnu=False):
    short_opts = []
    long_opts = []
    opt_names = {}
    opt_handlers = {}

    for opt in opts:
        long_opt, short_opt, default, handler = opt[:4]
        if short_opt:
            short_opts.append(handler.short_opt(short_opt))
            short_opt_ = "-%s" % short_opt
            opt_names[short_opt_] = long_opt
            opt_handlers[short_opt_] = handler

        long_opts.append(handler.long_opt(long_opt))
        long_opt_ = "--%s" % long_opt
        opt_names[long_opt_] = long_opt
        opt_handlers[long_opt_] = handler

    getopt_ = gnu and getopt.gnu_getopt or getopt.getopt

    try:
        opts, args = getopt_(args, "".join(short_opts), long_opts)
        for opt, arg in opts:
            opt_handlers[opt](opt_names[opt], arg, parsed_opts)
    except (getopt.GetoptError, ValueError) as e:
        raise error.CmdParseError(None, e)
    return args


def parse(opts, args):
    parsed_opts = {}
    for opt in opts:
        parsed_opts[opt[0]] = opt[2]
    parsed_args = _parse(args, opts, parsed_opts)
    return parsed_args, parsed_opts

