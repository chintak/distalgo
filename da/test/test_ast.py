
from da.compiler.ui import *

prog1 = """
class P(process):
    def setup():
        pass

    def run():
        --start
        a = 1
"""

ast1 = daast_from_str(prog1)
print(ast1.body[0].body[0].is_atomic)

prog2 = """
class P(process):
    def setup(b):
        pass

    def run():
        a = 1
        while True:
            sub()

    def sub():
        --start
        self.b = 1
"""

ast2 = daast_from_str(prog2)
print(ast2.body[0].body[1].is_atomic)
