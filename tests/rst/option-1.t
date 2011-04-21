@@ source @@
-a                  option 'alpha' description
-b ARG              option 'bravo' description
--charlie           option 'charlie' description...this is a really long description to force the description text to wrap.
--delta ARG         option 'delta' description
-f, --foxtrot       option 'foxtrot' description
-e ARG, --echo=ARG  option 'echo' description
@@ expected @@
-a            option 'alpha' description
-b ARG        option 'bravo' description
--charlie     option 'charlie' description...this is a really long description
              to force the description text to wrap.
--delta ARG   option 'delta' description
-f, --foxtrot
              option 'foxtrot' description
-e ARG, --echo=ARG
              option 'echo' description
