#!/usr/bin/env python
import ast
import z3

class SymEx:

    class Unsupported(ValueError): pass

    class Iterator:
        def __init__(self, seq, suc, i=0):
            self.seq = seq
            self.suc = suc
            self.i = i
            return

        def copy(self):
            return self.__class__(self.seq, self.suc, self.i)

        def next(self):
            if self.i < len(self.seq):
                obj = self.seq[self.i]
                self.i += 1
                return obj
            elif self.suc is None:
                return None
            else:
                return self.suc.next()

    def __init__(self, func):
        self.vars = {}
        self.conds = {}
        self.build(func)
        return

    def getvar(self, id):
        if id in self.vars:
            var = self.vars[id]
        else:
            var = self.vars[id] = z3.Int(id)
        return var

    def getexpr(self, t):
        if isinstance(t, ast.BinOp):
            left = self.getexpr(t.left)
            right = self.getexpr(t.right)
            if isinstance(t.op, ast.Add):
                return (left + right)
            elif isinstance(t.op, ast.Sub):
                return (left - right)
            elif isinstance(t.op, ast.Mult):
                return (left * right)
            else:
                raise Unsupported(t.op)

        elif isinstance(t, ast.Compare):
            assert len(t.ops) == 1
            assert len(t.comparators) == 1
            left = self.getexpr(t.left)
            right = self.getexpr(t.comparators[0])
            if isinstance(t.ops[0], ast.Eq):
                return (left == right)
            elif isinstance(t.ops[0], ast.NotEq):
                return (left != right)
            elif isinstance(t.ops[0], ast.Lt):
                return (left < right)
            elif isinstance(t.ops[0], ast.Gt):
                return (left > right)
            else:
                raise Unsupported(t.ops[0])

        elif isinstance(t, ast.Name):
            return self.getvar(t.id)

        elif isinstance(t, ast.Num):
            return z3.IntVal(t.n)

        else:
            raise Unsupported(t)

    def walk(self, t, eqs, it):
        if t is None:
            return
        elif isinstance(t, list):
            if it is not None:
                it = it.copy()
            it = self.Iterator(t, it)
            self.walk(it.next(), eqs, it)
            return

        if t in self.conds:
            a = self.conds[t]
        else:
            a = self.conds[t] = []
        a.append(eqs)
        if isinstance(t, ast.Assign):
            assert len(t.targets) == 1
            target = t.targets[0]
            assert isinstance(target, ast.Name)
            var = self.getvar(target.id)
            expr = self.getexpr(t.value)
            self.walk(it.next(), eqs+[(var == expr)], it)

        elif isinstance(t, ast.If):
            cond = self.getexpr(t.test)
            self.walk(t.body, eqs + [cond], it)
            self.walk(t.orelse, eqs + [z3.Not(cond)], it)
            self.walk(it.next(), eqs, it)

        else:
            self.walk(it.next(), eqs, it)

        return

    def build(self, func):
        assert isinstance(func, ast.FunctionDef), func
        for arg in func.args.args:
            self.getvar(arg.arg)
        self.walk(func.body, [], None)
        return

    def run(self, lines):
        ts = sorted(self.conds.keys(), key=lambda t: t.lineno)
        for t in ts:
            print('%2d: %s' % (t.lineno, lines[t.lineno-1]))
            for eqs in sorted(self.conds[t], key=lambda eqs: len(eqs)):
                s = z3.Solver()
                for eq in eqs:
                    s.add(eq)
                if s.check() == z3.sat:
                    print('*reachable*', s.model())
                    break
            else:
                print('*unreachable*')
        return

source = '''
def f(x, y):
    z = x+y*2
    if x < z+1:
        print('foo')
    elif z == y:
        print('baa')
    elif x == z+1:
        print('dood!')
    else:
        print('baz')
    return
'''
tree = ast.parse(source)
for func in tree.body:
    s = SymEx(func)
    s.run(source.splitlines())
