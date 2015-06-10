import sys
if sys.version_info<(3,0,0):
    from mikrotik import *
else:
    from mikrotik.mikrotik import *
