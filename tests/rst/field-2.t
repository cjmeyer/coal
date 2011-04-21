@@ source @@
:this is field 1:
    This is the text for field 1, paragraph 1.

    This is the text for field 1, paragraph 2.

:this is field 2.1.0: This is the text for field 1, paragraph 1. It is longer than previously to force wrapping of text.
@@ expected @@
this is field 1:
              This is the text for field 1, paragraph 1.

              This is the text for field 1, paragraph 2.

this is field 2.1.0:
              This is the text for field 1, paragraph 1. It is longer than
              previously to force wrapping of text.
