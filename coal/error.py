# error.py

import os

class SignatureError(Exception):
    """Exception raised due to a command function called with bad signature."""
    pass

class AbortError(Exception):
    """Exception raised due to an 'abort' condition."""
    pass

class ArgumentError(Exception):
    """Exception raised due to invalid method arguments."""
    pass

class RSTParseError(Exception):
    """Exception raised due to error parsing RST source."""
    pass

class CmdParseError(Exception):
    """Exception raised due to error parsing the command line options."""
    pass

