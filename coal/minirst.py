# minirst.py
"""
Minimal reStructuredText parser to parse command docstrings.

  - Paragraphs
  - Enumerated Lists (no auto-numbering)
  - Bullet Lists (must start with '-')
  - Option Lists (*nix style only)
  - Field Lists
  - Definition Lists
  - Literal Blocks
  - Containers
"""


import error
import re
import util


_bullet_re = re.compile(
    r"^(-|[0-9A-Za-z]+\.|\(?[0-9A-Za-z]+\)|\|)(?:$| +)")
_field_re = re.compile(
    r"^:(?![: ])([^:]*(?<! ):)(?: *$| +)")
_option_re = re.compile(
    r"""
     ^(--?[a-z-]+              # Match option flag (long or short)
     (?:[ =][a-zA-Z][\w-]*)?   # Match optional option argument
     (?:,?\ *                  # Match comma and any space betwen options
       --?[a-z-]+              # Match additional option flags (long or short)
       (?:[ =][a-zA-Z][\w-]*)? # Match additional option arguments
     )*)                       # Optional match more than one option
     (?:\ *$|\ \ +)            # Match to the end of the line or description""",
    re.VERBOSE)
_admonition_re = re.compile(
    r"\.\. (attention|caution|danger|error|hint|important|note|tip|warning):: *",
    re.IGNORECASE)
_interpret_re = re.compile(
    r":\w+:`\w+`|`\w+`:\w+:")

_admonitions = {
    "attention":"Attention:",
    "caution":"Caution:",
    "danger":"Danger!",
    "error":"Error:",
    "hint":"Hint:",
    "important":"Important:",
    "note":"Note:",
    "tip":"Tip:",
    "warning":"Warning!"
}


def _wrap(s, width, indent, subindent=None):
    subindent = subindent or indent
    return util.wrap(s, width, indent=indent, subindent=subindent)


def simple_block(src):
    """
    Parses out a simple block of continuous lines of text.
    """
    for i, v in enumerate(src):
        if not v[1]:
            return src[:i], src[i:]
    return src, []


def nested_block(src, shift_first=None, strip_indent=True):
    """
    Return a list of nested lines (indentation > 0).

    Groups all indented lines from ``src`` and optionally strips common
    indentation from them (enabled by default). Indentation relative to each
    other is maintained. This maintains the nested nature of the RST source
    text. Stripping away the common indentation of the grouped lines allowes the
    new list of lines to be treated as new RST source.

    The indentation of the first line of text may be specified independently of
    the rest of the text. If specified, the first line of text is stripped of
    the first ``shift_first`` characters and the line indentation is forced to
    0. This does not effect the common indentation of the rest of the grouped
    lines. If the rest of the lines share a common indentation of non-0, then
    they are stripped accordingly.

    :Parameters:
      - `src`: List of pre-processed Restructured Text lines.
      - `Shift_first`: Number of characters to strip from the first line.
      - `strip_indent`: Strip common indentation from block if specified.
    """
    end, last, indent = 0, len(src), None
    if shift_first is not None:
        end += 1
    while end < last:
        line = src[end]
        if line[1]:
            if line[0] < 1:
                break
            indent = (line[0] if indent is None else min(indent, line[0]))
        end += 1
    block, src[:end] = src[:end], []
    if block:
        if indent and strip_indent:
            for l in block:
                l[0] -= indent
        if shift_first is not None:
            block[0][0] = 0
            block[0][1] = block[0][1][shift_first:]
        while block and not block[0][1]:
            block.pop(0)
        while block and not block[-1][1]:
            block.pop(-1)
    return block, src


def parse_blank(src):
    """
    Parse a blank line.

    A blank line in RST text is used to denote the end of a block of content.
    Additional blank lines may also be inserted and should simply be ignored. In
    the case that a blank line is not consumed when parsing a block of content,
    this parse function will simply match and consume the line but result in no
    additional generated content.
    """
    if src[0][1]:
        return False, None, src
    src.pop(0)
    return True, None, src


def parse_nested(src):
    """
    Parses a nested block of RST text.

    A nested block of RST text is denoted by a line whose indentation level is
    greater than the previous block. This parse function always assumes the
    current indentation level is 0 so a nested block is matched whenever the
    first source lines indentation is greater than 0.

    A nested block is parsed by grouping the nested lines into a new list of
    pre-processed RST lines and then parsing them with the ``parse_body``
    function. This followes the nested/recursive nature of RST sources.
    """
    if src[0][0] == 0:
        return False, None, src
    nested, src = nested_block(src)
    content = parse_body(nested)

    def body(width, indent, **kw):
        return content(width, indent + "  ", **kw)

    return True, body, src


def parse_container(src):
    """
    Parse a RST container into the container content and name.

    The content of a container can be included in the formatted output by
    specifying the container type/name in the ``keep`` keyword argument passed
    to the returned format function. If the ``keep`` keyword is not specified or
    is specified as ``None``, then all containers will be kept.
    """
    if not (len(src) > 2 and src[1][1] == "" and
            src[0][1].startswith(".. container::")):
        return False, None, src
    name = src.pop(0)[1][14:].strip()
    nested, src = nested_block(src)
    body = parse_body(nested)

    def container(width, indent, keep=None, **kw):
        if keep is None or name in keep:
            return body(width, indent, keep=keep, **kw)

    return True, container, src


def parse_admonition(src):
    """
    Parse admonition blocks.

    Admonition blocks contain specially marked topics. This are marked similar
    to containers but are rendered so as to draw attention to the text. All
    valid admonitions are defined in the ``_admonitions`` dictionary which map
    the understood admonition directives to their topic titles.
    """
    m = _admonition_re.match(src[0][1])
    if not m:
        return False, None, src
    title = _admonitions[m.group(1).lower()]
    nested, src = nested_block(src, shift_first=m.end(0))
    body = parse_body(nested)

    def admonition(width, indent, **kw):
        return "%s%s\n%s" % (indent, title, body(width, indent + "  ", **kw))

    return True, admonition, src


def parse_list(item_match, src, max_keywidth=None, min_space=1, vspace=False):
    """
    Parse a RST list of items.

    The match function passed in via ``item_match`` should return an object
    with two attributes: ``key`` and ``offset``. The value in ``key`` is the
    item key text to be used when rendering the output. It should not contain
    any addition whitespace; additional whitespace will be added by the format
    function. The value in ``offset`` is the offset from the start of the first
    line in the RST source to the body text of the item.

    :Parameters:
      - `item_match`: The item match function
      - `src`: The list of RST source lines
      - `max_keywidth`: The maximum width of the key field in the output
      - `min_space`: The minimum whitespace between key field and item body
           formatted output text
      - `vspace`: If ``True``, insert a blank line between every list item
    """
    m = item_match(src)
    if not m:
        return False, None, src
    items = []
    while m:
        block, src = nested_block(src, shift_first=m.offset)
        items.append((m.key, parse_body(block)))
        m = src and item_match(src)

    keywidth = max(len(item[0]) for item in items) + min_space
    if max_keywidth is not None:
        keywidth = min(keywidth, max_keywidth)

    def list_(width, indent, **kw):
        hanging = indent + (keywidth * " ")
        offset = len(indent) + keywidth
        result = []
        for item in items:
            content = item[1](width, hanging, **kw)
            if len(item[0]) + min_space > keywidth:
                content = indent + item[0] + "\n" + content
            else:
                content = indent + item[0].ljust(keywidth) + content[offset:]
            if result and (vspace or result[-1].find("\n\n") != -1):
                result.append("")
            result.append(content)
        return "\n".join(result)

    return True, list_, src


class ListItemMatch(object):
    def __init__(self, key, offset):
        self.key, self.offset = key, offset


def match_list(item_re, src):
    m = item_re.match(src[0][1])
    if not m:
        return None
    return ListItemMatch(m.group(1), m.end(0))

# Match and parse bullet and numbered lists.
def match_bullet(src):
    return match_list(_bullet_re, src)
def parse_bullet(src):
    return parse_list(match_bullet, src)

# Match and parse *nix style option lists.
def match_option(src):
    return match_list(_option_re, src)
def parse_option(src):
    return parse_list(match_option, src, max_keywidth=14, min_space=2)

# Match and parse field lists.
def match_field(src):
    return match_list(_field_re, src)
def parse_field(src):
    return parse_list(match_field, src, max_keywidth=14, min_space=2)

# Match definition lists. Note that definition list matching must be performed
# after all other lists matches are attempted and prior to matching a paragraph.
def match_definition(src):
    if len(src) > 1 and src[0][0] < src[1][0]:
        return ListItemMatch(src[0][1], len(src[0][1]))
    return None
def parse_definition(src):
    return parse_list(match_definition, src, max_keywidth=2, min_space=2,
                      vspace=True)


def inline_code(s):
    return "\"%s\"" % s

_inline_handlers = [
    ("code", inline_code)
]

def _parse_interpreted(src):
    """
    Parse inline interpreted text.

    Restructured text may contain custom inline constructs. These constructs
    allow application specific formatting of the enclosed strings. Such a
    construct is written as ":id:`text to format`" or "`text to format`:id:"
    where "id" is some sort of identifier used to specify how to format the
    specified text.
    """
    for h in _inline_handlers:
        def interpret(m):
            return h[1](m.group(1))
        src = re.sub(r":%s:`([\w ]+)`" % h[0], interpret, src)
        src = re.sub(r"`([\w ]+)`:%s:" % h[0], interpret, src)
    return src


def _parse_inline(src):
    return _parse_interpreted(" ".join(l[1] for l in src).replace('``', '"'))


def parse_paragraph(src):
    """
    Parse RST paragraph.

    Reads text up to the next blank line and joins all the lines into a block of
    paragraph text. When formatted, paragraph text is wrapped at the specified
    maximum width with the specified indentation.

    A paragraph may also specify that it is followed by a literal block. In this
    case the content includes not only the paragraph text by the literal text as
    well. This is handled transparently and requires no additional support from
    the caller.
    """
    block, src = simple_block(src)
    if not block:
        return False, None, src

    para = _parse_inline(block)
    literal = None
    if para.endswith("::"):
        if para == "::":
            para = None
        elif para.endswith(" ::"):
            para = para[:-3]
        else:
            para = para[:-1]
        literal, src = nested_block(src)

    def literal_line(indent, l):
        return l[1] and "%s  %s%s" % (indent, l[0] * " ", l[1]) or ""

    def paragraph(width, indent, **kw):
        result = []
        if para:
            result.append(_wrap(para, width, indent))
        if literal:
            literal_ = [literal_line(indent, l) for l in literal]
            result.append("\n".join(literal_))
        return "\n\n".join(result)

    return True, paragraph, src


_transitions = [
    parse_blank,
    parse_nested,
    parse_container,
    parse_admonition,
    parse_bullet,
    parse_option,
    parse_field,
    parse_definition,
    parse_paragraph
]


def parse_body(src):
    """
    Parse the body of an RST document.

    An RST document is parsed as a set of blocks of content and content type.
    Each block is parsed via a *transition* or *parse* function. Each *parse*
    function returns a 3-tuple of a boolean specifying if the block type
    matched the type parseable by the function, a new format function used to
    generate the resulting formatted text, and the list of remaining RST lines
    to be parsed.

    The *parse* functions are specified in the ``_transitions`` list. Each
    function is tried in sequence on the current source input. If non of the
    function where able to successfully match the current source, an exception
    is raised. If a function does successfully match the input, then the
    returned format function is appended to the list of blocks and the source
    is again attempted to be parsed by starting at the begging of the
    ``_transitions`` list.

    This function may be called recursively via the *parse* functions in order
    to parse nested RST blocks of text.
    """
    blocks = []
    while src:
        for t in _transitions:
            matched, block, src = t(src)
            if matched:
                if block:
                    blocks.append(block)
                break
        else:
            raise error.RSTParseError("invalid ReST source")

    def body(width, indent, **kw):
        result = []
        for b in blocks:
            block_ = b(width, indent, **kw)
            if block_ is not None:
                result.append(block_)
        return "\n\n".join(result)

    return body


def format_rst(src, width=80, indent=None, **kw):
    indent = indent or ""
    lines = []
    for line in src.splitlines():
        line_ = line.lstrip()
        lines.append([line_ and len(line) - len(line_) or 0, line_])
    if lines:
        shared_indent = min(l[0] for l in lines if l[1])
        for l in lines:
            l[0] -= shared_indent
    rst = parse_body(lines)
    return rst(width, indent, **kw)


if __name__ == "__main__":
    with open(sys.argv[1], "r") as f:
        print format_rst(f.read(), int(sys.argv.get(2, 80)), keep=sys.argv[3:])

