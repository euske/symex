#!/usr/bin/env python
#
#  df0.py - very basic dataflow analysis for Python.
#
#  Assumptions:
#   - Variables can have multiple types.
#   - Functions are polymorphic.
#   - The same types for function arguments = the same behavior.
#     (so it can be cached.)
#   - Global variables have constant types.
#
#  Supported:
#   - Nested scopes.
#   - Dynamic typing.
#   - Function call.
#   - Crappy type inference. (arg1 op arg2) => arg1
#
#  Unsupported:
#   - Classes / lists / dicts.
#   - Optional / keyword arguments.
#   - Builtin functions.
#   - Module imports.
#   - Fancy control statements (yield, etc.)
#   - Efficiency. (All the values are copied every time.)
#


import ast


##  optype: infers a data type.
##
def optype(value1, op, value2):
    # XXX
    return value1.copy()


##  Ref: unique identifier for variables.
##
class Ref:

    RETURN = '_RETURN' # Special variable for a return value.

    def __init__(self, space, name):
        self.space = space
        self.name = name
        return

    def __repr__(self):
        return f'<{self.space}.{self.name}>'


##  Namespace: nested variable scope.
##
class Namespace:

    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.spaces = {}
        self.refs = {}
        return

    def __repr__(self):
        return f'{self.name}'

    def add(self, name):
        if name in self.refs:
            ref = self.refs[name]
        else:
            ref = self.refs[name] = Ref(self, name)
        return ref

    def lookup(self, name):
        space = self
        while space is not None:
            if name in space.refs:
                return space.refs[name]
            space = space.parent
        raise KeyError(name)

    def build(self, body):
        for tree in body:
            self.build1(tree)
        return

    def build1(self, tree):
        if isinstance(tree, ast.FunctionDef):
            space = Namespace(self.name+'.'+tree.name, self)
            self.spaces[tree.name] = space
            for t in tree.args.args:
                space.add(t.arg)
            space.build(tree.body)
            ref = self.add(tree.name)
            Function.register(ref, space, tree)
        elif isinstance(tree, ast.If):
            self.build(tree.body)
            self.build(tree.orelse)
        elif isinstance(tree, ast.While):
            self.build(tree.body)
            self.build(tree.orelse)
        elif isinstance(tree, ast.For):
            self.add(tree.target.id)
            self.build(tree.body)
            self.build(tree.orelse)
        elif isinstance(tree, ast.Assign):
            for t in tree.targets:
                self.add(t.id)
        elif isinstance(tree, ast.AugAssign):
            self.add(tree.target.id)
        elif isinstance(tree, ast.Expr):
            pass
        elif isinstance(tree, ast.Return):
            self.add(Ref.RETURN)
        elif isinstance(tree, ast.Break):
            pass
        elif isinstance(tree, ast.Continue):
            pass
        elif isinstance(tree, ast.Pass):
            pass
        else:
            raise SyntaxError(tree)
        return


##  Function: user defined functions.
##
class Function:

    functions = {}

    @classmethod
    def register(klass, ref, space, tree):
        klass.functions[ref] = Function(space, tree)
        return

    @classmethod
    def get(klass, ref):
        return klass.functions[ref]

    def __init__(self, space, tree):
        self.space = space
        self.tree = tree
        self.bbs = {}
        return

    def __repr__(self):
        return f'<Function {self.tree.name}>'

    def apply(self, args, values):
        key = tuple(map(repr, args))
        if key in self.bbs:
            # Cached.
            bb = self.bbs[key]
        else:
            # Not cached.
            values = { k:v.copy() for (k,v) in values.items() }
            for (arg,value) in zip(self.tree.args.args, args):
                ref = self.space.lookup(arg.arg)
                if ref not in values:
                    values[ref] = set()
                values[ref].update(value)
            bb = BBlock(self.space, values)
            bb.perform(self.tree.body)
            self.bbs[key] = bb
        ref = self.space.lookup(Ref.RETURN)
        return bb.values.get(ref)

    def dump(self):
        print(f'== {self} ==')
        for bb in self.bbs.values():
            d = {}
            for ref in self.space.refs.values():
                value = bb.values.get(ref)
                print(f'{ref}: {value}')
            print()
        return


##  BBlock: uninterrupted sequence of statements (Basic Blocks).
##
class BBlock:

    def __init__(self, space, values):
        self.space = space
        self.values = { k:v.copy() for (k,v) in values.items() }
        return

    def merge(self, values1, values2):
        for (ref,value) in values1.items():
            if ref in self.values:
                self.values[ref].update(value)
            else:
                self.values[ref] = value.copy()
        for (ref,value) in values2.items():
            if ref in self.values:
                self.values[ref].update(value)
            else:
                self.values[ref] = value.copy()
        return

    def eval(self, tree):
        if isinstance(tree, ast.Name):
            ref = self.space.lookup(tree.id)
            return self.values.get(ref)
        elif isinstance(tree, ast.Constant):
            return { type(tree.value) }
        elif isinstance(tree, ast.BinOp):
            value1 = self.eval(tree.left)
            value2 = self.eval(tree.right)
            return optype(value1, tree.op, value2)
        elif isinstance(tree, ast.UnaryOp):
            value = self.eval(tree.operand)
            return optype(None, tree.op, value)
        elif isinstance(tree, ast.Call):
            values = set()
            for func in self.eval(tree.func):
                if isinstance(func, Function):
                    args = [ self.eval(arg1) for arg1 in tree.args ]
                    value = func.apply(args, self.values)
                    values.update(value)
            return values
        else:
            raise SyntaxError(tree)

    def perform(self, body):
        for tree in body:
            self.perform1(tree)
        return

    def perform1(self, tree):
        if isinstance(tree, ast.FunctionDef):
            ref = self.space.lookup(tree.name)
            self.values[ref] = { Function.get(ref) }
        elif isinstance(tree, ast.If):
            bb1 = BBlock(self.space, self.values)
            bb1.perform(tree.body)
            bb2 = BBlock(self.space, self.values)
            bb2.perform(tree.orelse)
            self.merge(bb1.values, bb2.values)
        elif isinstance(tree, ast.While):
            bb1 = BBlock(self.space, self.values)
            bb1.perform(tree.body)
            bb2 = BBlock(self.space, self.values)
            bb2.perform(tree.orelse)
            self.merge(bb1.values, bb2.values)
        elif isinstance(tree, ast.For):
            bb1 = BBlock(self.space, self.values)
            bb1.perform(tree.body)
            bb2 = BBlock(self.space, self.values)
            bb2.perform(tree.orelse)
            self.merge(bb1.values, bb2.values)
        elif isinstance(tree, ast.Assign):
            value = self.eval(tree.value)
            for t in tree.targets:
                ref = self.space.lookup(t.id)
                self.values[ref] = value
        elif isinstance(tree, ast.AugAssign):
            value1 = self.eval(tree.target)
            value2 = self.eval(tree.value)
            ref = self.space.lookup(tree.target.id)
            self.values[ref] = optype(value1, tree.op, value2)
        elif isinstance(tree, ast.Expr):
            value = self.eval(tree.value)
        elif isinstance(tree, ast.Return):
            if tree.value is not None:
                value = self.eval(tree.value)
                ref = self.space.lookup(Ref.RETURN)
                self.values[ref] = value
        elif isinstance(tree, ast.Break):
            pass
        elif isinstance(tree, ast.Continue):
            pass
        elif isinstance(tree, ast.Pass):
            pass
        else:
            raise SyntaxError(tree)
        return


# demo
source = '''
def print(x):
    return x

def f(x, y):
    z = x
    z += y*2
    if x < z+1:
        print('foo')
    elif z == y:
        print('baa')
    elif x == z+1:
        z = print('dood!')
    else:
        print('baz')
    return z

print(f(3,4))
'''
tree = ast.parse(source)
root = Namespace('')
root.build(tree.body)
bb = BBlock(root, {})
bb.perform(tree.body)
for f in Function.functions.values():
    f.dump()
