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
#


import ast


##  optype: infers a data type.
##
def optype(value1, op, value2):
    v = set()
    for v1 in value1:
        for v2 in value2:
            v.add(v1.binop(op, v2))
    return v


##  idtree: returns a tree identifier.
##
def idtree(tree):
    if isinstance(tree, ast.ClassDef):
        return f'class:{tree.name}:{tree.lineno}:{tree.col_offset}'
    elif isinstance(tree, ast.FunctionDef):
        return f'def:{tree.name}:{tree.lineno}:{tree.col_offset}'
    elif isinstance(tree, ast.Lambda):
        return f'lambda:{tree.lineno}:{tree.col_offset}'
    else:
        raise ValueError(tree)


##  Type: user defined types.
##
class Type:

    types = {}

    @classmethod
    def get(klass, value):
        return klass.types[type(value)]

    @classmethod
    def add(klass, key, value):
        klass.types[key] = value
        return

    functions = {}

    @classmethod
    def register(klass, tree, func):
        klass.functions[idtree(tree)] = func
        return

    @classmethod
    def lookup(klass, tree):
        return klass.functions[idtree(tree)]

    def uniop(self, op):
        # XXX
        return self

    def binop(self, op, value):
        # XXX
        return value

    def getitem(self, name):
        # XXX
        return self

    def setitem(self, name, value):
        # XXX
        return

    def getattr(self, name):
        # XXX
        return self

    def setattr(self, name, value):
        # XXX
        return

class BasicType(Type):

    def __init__(self, type):
        self.type = type
        return

    def __repr__(self):
        return repr(self.type)

Type.add(int, BasicType(int))
Type.add(str, BasicType(str))
Type.add(bool, BasicType(bool))
Type.add(float, BasicType(float))


##  Function: user defined functions.
##
class Function(Type):

    def __init__(self, space, tree):
        self.space = space
        self.tree = tree
        self.bbs = {}
        return

    def __repr__(self):
        return f'<Function {idtree(self.tree)}>'

    def apply(self, args, envs):
        #print(f'apply: {self}({args})')
        key = repr(args)
        if key in self.bbs:
            # Cached.
            bb = self.bbs[key]
        else:
            # Not cached.
            bb = self.bbs[key] = BBlock(self.space, envs)
            for (arg,value) in zip(self.tree.args.args, args):
                ref = self.space.lookup(arg.arg)
                bb.values[ref] = value.copy()
            if isinstance(self.tree, ast.Lambda):
                bb.retval = bb.eval(self.tree.body)
            else:
                bb.perform(self.tree.body)
        return bb.retval

    def dump(self):
        print(f'== {self} ==')
        for bb in self.bbs.values():
            for ref in self.space.refs.values():
                value = bb.values.get(ref)
                print(f'{ref}: {value}')
            print()
        return


##  Ref: unique identifier for variables.
##
class Ref:

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

    def root(self):
        space = self
        while space.parent is not None:
            space = space.parent
        return space

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
            self.add(tree.name)
            func = Function(space, tree)
            Type.register(tree, func)
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
        elif isinstance(tree, ast.Global):
            space = self.root()
            for name in tree.names:
                self.refs[name] = space.add(name)
        elif isinstance(tree, ast.Expr):
            pass
        elif isinstance(tree, ast.Return):
            pass
        elif isinstance(tree, ast.Break):
            pass
        elif isinstance(tree, ast.Continue):
            pass
        elif isinstance(tree, ast.Pass):
            pass
        else:
            raise SyntaxError(tree)
        return


##  BBlock: uninterrupted sequence of statements (Basic Blocks).
##
class BBlock:

    def __init__(self, space, envs):
        self.space = space
        self.envs = envs
        self.values = {}
        self.retval = None
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
            if ref in self.values:
                return self.values[ref]
            else:
                for env in self.envs:
                    if ref in env:
                        return env[ref]
                # Undefined value.
                raise ValueError(f'Undefined: {ref}')
        elif isinstance(tree, ast.Constant):
            return { Type.get(tree.value) }
        elif isinstance(tree, ast.BinOp):
            value1 = self.eval(tree.left)
            value2 = self.eval(tree.right)
            return optype(value1, tree.op, value2)
        elif isinstance(tree, ast.UnaryOp):
            value = self.eval(tree.operand)
            return { v.uniop(tree.op) for v in value }
        elif isinstance(tree, ast.Call):
            values = set()
            for func in self.eval(tree.func):
                if isinstance(func, Function):
                    args = [ self.eval(arg1) for arg1 in tree.args ]
                    value = func.apply(args, (self.values,)+self.envs)
                    values.update(value)
            return values
        elif isinstance(tree, ast.Lambda):
            space = Namespace(idtree(tree), self.space)
            for t in tree.args.args:
                space.add(t.arg)
            func = Function(space, tree)
            Type.register(tree, func)
            return { func }
        else:
            raise SyntaxError(tree)

    def perform(self, body):
        for tree in body:
            self.perform1(tree)
        return

    def perform1(self, tree):
        if isinstance(tree, ast.FunctionDef):
            ref = self.space.lookup(tree.name)
            self.values[ref] = { Type.lookup(tree) }
        elif isinstance(tree, ast.If):
            envs = (self.values,)+self.envs
            bb1 = BBlock(self.space, envs)
            bb1.perform(tree.body)
            bb2 = BBlock(self.space, envs)
            bb2.perform(tree.orelse)
            self.merge(bb1.values, bb2.values)
        elif isinstance(tree, ast.While):
            envs = (self.values,)+self.envs
            bb1 = BBlock(self.space, envs)
            bb1.perform(tree.body)
            bb2 = BBlock(self.space, envs)
            bb2.perform(tree.orelse)
            self.merge(bb1.values, bb2.values)
        elif isinstance(tree, ast.For):
            envs = (self.values,)+self.envs
            bb1 = BBlock(self.space, envs)
            bb1.perform(tree.body)
            bb2 = BBlock(self.space, envs)
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
        elif isinstance(tree, ast.Global):
            pass
        elif isinstance(tree, ast.Expr):
            value = self.eval(tree.value)
        elif isinstance(tree, ast.Return):
            if tree.value is not None:
                value = self.eval(tree.value)
                self.retval = value
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

g = f
h = lambda x,y: g(x+1,y)
print(h(3,4))
'''
tree = ast.parse(source)
root = Namespace('')
root.build(tree.body)
bb = BBlock(root, ())
bb.perform(tree.body)
for f in Type.functions.values():
    f.dump()
