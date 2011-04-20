# test_minirst.py


import glob
import os
import unittest2 as unittest

from coal import minirst


def re_test(re_, pass_):
    def decorator(fn_):
        def fn(self):
            if pass_:
                def test(text, key, offset):
                    m = re_.match(text)
                    self.assertIsNotNone(m)
                    self.assertEqual(m.end(0), offset)
                    self.assertEqual(m.group(1), key)
            else:
                def test(text, key, offset):
                    self.assertIsNone(re_.match(text))
            fn_(self, test)
        return fn
    return decorator


class MiniRSTTest(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def rst_test(self, fname):
        source, expected = [], []
        with open(os.path.join(os.path.dirname(__file__), "rst", fname)) as f:
            kw = {}
            for l in f:
                l = l.strip()
                if l.startswith("@@ source") and l.endswith("@@"):
                    if l.startswith("@@ source:"):
                        kw.update(eval("dict(%s)" % l[10:-2]))
                    break
            else:
                raise Exception("No ReST source found")
            for l in f:
                if l.strip() == "@@ expected @@":
                    break
                source.append(l.rstrip("\n"))
            for l in f:
                expected.append(l.rstrip("\n"))
        source = "\n".join(source)
        expected = "\n".join(expected)
        self.assertEqual(minirst.format_rst(source, **kw).splitlines(),
                         expected.splitlines())

    @re_test(minirst._bullet_re, True)
    def test_bullet_item_re(self, test):
        test("1. Lorem ipsum dolor.", "1.", 3)
        test("2.   Lorem ipsum dolor.", "2.", 5)
        test("34. Lorem ipsum dolor.", "34.", 4)
        test("a)    Lorem ipsum dolor.", "a)", 6)
        test("B)   Lorem ipsum dolor.", "B)", 5)
        test("56) Lorem ipsum dolor.", "56)", 4)

    @re_test(minirst._option_re, True)
    def test_option_item_re(self, test):
        test("-b", "-b", 2)
        test("-b ARG", "-b ARG", 6)
        test("-b ARG  Option description", "-b ARG", 8)
        test("-b ARG   Option description", "-b ARG", 9)
        test("--long-option", "--long-option", 13)
        test("--long-option  Option description", "--long-option", 15)
        test("--long-option=ARG", "--long-option=ARG", 17)
        test("--long-option ARG  Option description", "--long-option ARG", 19)
        test("-b, --long-option ", "-b, --long-option", 18)
        test("-b, --long-option, --another-option", "-b, --long-option, --another-option", 35)
        test("-b, --long-option ARG  Option description", "-b, --long-option ARG", 23)
        test("-b ARG, --long-option ARG  Option description", "-b ARG, --long-option ARG", 27)
        test("-b --long-option ARG  Option description", "-b --long-option ARG", 22)

    @re_test(minirst._field_re, True)
    def test_field_item_re(self, test):
        test(":field key:  field value", "field key:", 13)
        test(":key:    value", "key:", 9)

def build_test(p):
    def test(self):
        self.rst_test(p)
    return test

for fname in glob.glob(os.path.join(os.path.dirname(__file__), "rst", "*.tst")):
    test_name = "test_%s" % os.path.basename(fname)[:-4].replace("-", "_")
    setattr(MiniRSTTest, test_name, build_test(fname)) 

