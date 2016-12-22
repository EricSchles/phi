"""
The Phi DSL is all about combining functions in useful ways, enabling a declarative approach that can improve clarity, readability and lead to shorter code. All valid expression of the DSL can be compiled to a function using `P.Seq` or applied to a value using `P.Pipe`.

Phi offers the following constructs, **try to read their documentation in order**:

* **`Functions`**: any function of arity 1 is an element of the language
* **`Values`**: any value is transformed into a constant function using `phi.dsl.Expression.Val`
* **`phi.dsl.Expression.Seq`**: allows to sequentially compose functions
* **`phi.dsl.Expression.Branch`**: lets to create a branched computation that returns a list with the results of each branch
* **`phi.dsl.Expression.Val`**: allows you to specify an input value, compiles to a (constant) function that returns the same value no matter the input
* **`phi.dsl.Expression.With`**: lets you to specify a context manager for the expresion (uses the `with` statemente)
* **`phi.dsl.Expression.Rec`**: lets to create a branched computation with named branches that returns a record-like structure with the results of each branch
* **`phi.dsl.Expression.Read` & `phi.dsl.Expression.Write`**: allow you to create a reference to the value at some point and read it latter on.
* **`phi.dsl.Expression.If`**: allows you to create conditional computation

Any expresion can appear inside any other expresion in a nested fasion. They correct way to think about this is that each sub-expression will be compiled to a function of arity 1, therefore from the parent expresion's point of view all of its elements are just functions.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from .utils import identity
from . import utils
from abc import ABCMeta, abstractmethod
from inspect import isclass
import functools
from .lambdas import Lambda


###############################
# Helpers
###############################
class _ReadProxy(object):
    """docstring for _ReadProxy."""

    def __init__(self, __builder__):
        self.__builder__ = __builder__

    def __getitem__(self, name):
        return self.__do__(name)

    def __getattr__(self, name):
        return self.__do__(name)

    def __call__ (self, name):
        return self.__do__(name)

    def __do__(self, name):

        g = lambda z, state: (state[name], state)

        return self.__builder__.__then__(g)


class _WriteProxy(object):
    """docstring for _WriteProxy."""

    def __init__(self, __builder__):
        self.__builder__ = __builder__

    def __getitem__(self, ref):
        return self.__do__([ref])

    def __getattr__ (self, ref):
        return self.__do__([ref])

    def __call__ (self, *refs):
        return self.__do__(refs)

    def __do__(self, refs):

        def g(x, state):
            update = {ref: x for ref in refs}
            next_state = utils.merge(state, update)

            return x, next_state

        return self.__builder__.__then__(g)

class _ObjectProxy(object):
    """docstring for Underscore."""

    def __init__(self, __builder__):
        self.__builder__ = __builder__

    def __getattr__(self, name):

        def method_proxy(*args, **kwargs):
            f = lambda x: getattr(x, name)(*args, **kwargs)
            return self.__builder__.__then__(utils.lift(f))

        return method_proxy

class _RecordProxy(object):
    """docstring for _RecordProxy."""

    def __init__(self, __builder__):
        self.__builder__ = __builder__

    def __call__(self, **branches):
        gs = { key : _parse(value)._f for key, value in branches.items() }

        @utils.lift
        def h(x):
            return _RecordObject(**{key: g(x) for key, g in gs.items() })

        return self.__builder__.__then__(h)

    def __getattr__ (self, attr):
        f = lambda x: getattr(x, attr)
        return self.__builder__.__then__(utils.lift(f))

    def __getitem__(self, key):
        f = lambda x: x[key]
        return self.__builder__.__then__(utils.lift(f))


class Ref(object):
    """
Returns an object that helps you to inmediatly create and [read](https://cgarciae.github.io/phi/dsl.m.html#phi.dsl.Read) [references](https://cgarciae.github.io/phi/dsl.m.html#phi.dsl.Ref).

**Creating Refences**

You can manually create a [Ref](https://cgarciae.github.io/phi/dsl.m.html#phi.dsl.Ref) outside the DSL using `Ref` and then pass to as/to a `phi.dsl.Expression.Read` or `phi.dsl.Expression.Write` expression. Here is a contrived example

from phi import P, Ref

r = Ref('r')

assert [600, 3, 6] == P.Pipe(
    2,
    P + 1, {'a'},  # a = 2 + 1 = 3
    P * 2, {'b'},  # b = 3 * 2 = 6
    P * 100, {'c', r },  # c = r = 6 * 100 = 600
    ['c', 'a', 'b']
)

assert r() == 600

**Reading Refences from the Current Context**

While the expression `Read.a` with return a function that will discard its argument and return the value of the reference `x` in the current context, the expression `Ref.x` will return the value inmediatly, this is useful when using it inside pyton lambdas.

Read.x(None) <=> Ref.x

As an example

from phi import P, Obj, Ref

assert {'a': 97, 'b': 98, 'c': 99} == P.Pipe(
    "a b c", Obj
    .split(' ').Write.keys  # keys = ['a', 'b', 'c']
    .map(ord),  # [ord('a'), ord('b'), ord('c')] == [97, 98, 99]
    lambda it: zip(Ref.keys, it),  # [('a', 97), ('b', 98), ('c', 99)]
    dict   # {'a': 97, 'b': 98, 'c': 99}
)

    """
    def __init__(self, name, value=utils.NO_VALUE):
        super(Ref, self).__init__()
        self.name = name
        """
The reference name. Can be though a key in a dictionary.
        """
        self.value = value
        """
The value of the reference. Can be though a value in a dictionary.
        """

    def __call__(self, *optional):
        """
Returns the value of the reference. Any number of arguments can be passed, they will all be ignored.
        """
        if self.value is utils.NO_VALUE:
            raise Exception("Trying to read Ref('{0}') before assignment".format(self.name))

        return self.value

    def write(self, x):
        """
Sets the value of the reference equal to the input argument `x`. Its also an identity function since it returns `x`.
        """
        self.value = x

        return x

class _RecordObject(dict):
    """docstring for DictObject."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __getattr__ (self, attr):
        return self[attr]

    def __setitem__(self, key, item):
        self.__dict__[key] = item

    def __getitem__(self, key):
        return self.__dict__[key]

    def __repr__(self):
        return repr(self.__dict__)

    def __len__(self):
        return len(self.__dict__)

    def __delitem__(self, key):
        del self.__dict__[key]

    def clear(self):
        return self.__dict__.clear()

    def copy(self):
        return self.__dict__.copy()

    def has_key(self, k):
        return self.__dict__.has_key(k)

    def pop(self, k, d=None):
        return self.__dict__.pop(k, d)

    def update(self, *args, **kwargs):
        return self.__dict__.update(*args, **kwargs)

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()

    def items(self):
        return self.__dict__.items()

    def pop(self, *args):
        return self.__dict__.pop(*args)

    def __cmp__(self, dict):
        return cmp(self.__dict__, dict)

    def __contains__(self, item):
        return item in self.__dict__

    def __iter__(self):
        return iter(self.__dict__)

    def __unicode__(self):
        return unicode(repr(self.__dict__))

class _WithContextManager(object):

    WITH_GLOBAL_CONTEXT = utils.NO_VALUE

    def __init__(self, new_scope):
        self.new_scope = new_scope
        self.old_scope = _WithContextManager.WITH_GLOBAL_CONTEXT

    def __enter__(self):
        _WithContextManager.WITH_GLOBAL_CONTEXT = self.new_scope

    def __exit__(self, *args):
        _WithContextManager.WITH_GLOBAL_CONTEXT = self.old_scope
###############################
# DSL Elements
###############################



class Expression(Lambda):
    """
All elements of this language are callables (implement `__call__`) of arity 1.

** Examples **

Compiling a function just returns back the function

    Seq(f) == f

and piping through a function is just the same a applying the function

    Pipe(x, f) == f(x)
    """

    def Pipe(self, *sequence, **kwargs):
        """
`Pipe` runs any `phi.dsl.Expression`. Its highly inspired by Elixir's [|> (pipe)](https://hexdocs.pm/elixir/Kernel.html#%7C%3E/2) operator.

**Arguments**

* ***sequence**: any variable amount of expressions. All expressions inside of `sequence` will be composed together using `phi.dsl.Expression.Seq`.
* ****kwargs**: `Pipe` forwards all `kwargs` to `phi.builder.Builder.Seq`, visit its documentation for more info.

The expression

    Pipe(*sequence, **kwargs)

is equivalent to

    Seq(*sequence, **kwargs)(None)

Normally the first argument or `Pipe` is a value, that is reinterpreted as a `phi.dsl.Expression.Val`, therfore, the input `None` is discarded.

**Examples**

    from phi import P

    def add1(x): return x + 1
    def mul3(x): return x * 3

    x = P.Pipe(
        1,     #input
        add1,  #1 + 1 == 2
        mul3   #2 * 3 == 6
    )

    assert x == 6

The previous using [lambdas](https://cgarciae.github.io/phi/lambdas.m.html) to create the functions

    from phi import P

    x = P.Pipe(
        1,      #input
        P + 1,  #1 + 1 == 2
        P * 3   #2 * 3 == 6
    )

    assert x == 6

**Also see**

* `phi.builder.Builder.Seq`
* [dsl](https://cgarciae.github.io/phi/dsl.m.html)
* [Compile](https://cgarciae.github.io/phi/dsl.m.html#phi.dsl.Compile)
* [lambdas](https://cgarciae.github.io/phi/lambdas.m.html)
        """
        return self.Seq(*sequence, **kwargs)(None)

    def ThenAt(self, n, f, *args, **kwargs):
        """
`ThenAt` enables you to create a partially apply many arguments to a function, the returned partial expects a single arguments which will be applied at the `n`th position of the original function.

**Arguments**

* **n**: position at which the created partial will apply its awaited argument on the original function.
* **f**: function which the partial will be created.
* **args & kwargs**: all `*args` and `**kwargs` will be passed to the function `f`.
* `_return_type = None`: type of the returned `builder`, if `None` it will return the same type of the current `builder`. This special kwarg will NOT be passed to `f`.

You can think of `n` as the position that the value being piped down will pass through the `f`. Say you have the following expression

    D == fun(A, B, C)

all the following are equivalent

    from phi import P, Pipe, ThenAt

    D == Pipe(A, ThenAt(1, fun, B, C))
    D == Pipe(B, ThenAt(2, fun, A, C))
    D == Pipe(C, ThenAt(3, fun, A, B))

you could also use the shortcuts `Then`, `Then2`,..., `Then5`, which are more readable

    from phi import P, Pipe

    D == Pipe(A, P.Then(fun, B, C))
    D == Pipe(B, P.Then2(fun, A, C))
    D == Pipe(C, P.Then3(fun, A, B))

There is a special case not discussed above: `n = 0`. When this happens only the arguments given will be applied to `f`, this method it will return a partial that expects a single argument but completely ignores it

    from phi import P

    D == Pipe(None, P.ThenAt(0, fun, A, B, C))
    D == Pipe(None, P.Then0(fun, A, B, C))

**Examples**

Max of 6 and the argument:

    from phi import P

    assert 6 == P.Pipe(
        2,
        P.Then(max, 6)
    )

Previous is equivalent to

    assert 6 == max(2, 6)

Open a file in read mode (`'r'`)

    from phi import P

    f = P.Pipe(
        "file.txt",
        P.Then(open, 'r')
    )

Previous is equivalent to

    f = open("file.txt", 'r')

Split a string by whitespace and then get the length of each word

    from phi import P

    assert [5, 5, 5] == P.Pipe(
        "Again hello world",
        P.Then(str.split, ' ')
        .Then2(map, len)
    )

Previous is equivalent to

    x = "Again hello world"

    x = str.split(x, ' ')
    x = map(len, x)

    assert [5, 5, 5] == x

As you see, `Then2` was very useful because `map` accepts and `iterable` as its `2nd` parameter. You can rewrite the previous using the [PythonBuilder](https://cgarciae.github.io/phi/python_builder.m.html) and the `phi.builder.Builder.Obj` object

    from phi import P, Obj

    assert [5, 5, 5] == P.Pipe(
        "Again hello world",
        Obj.split(' '),
        P.map(len)
    )

**Also see**

* `phi.builder.Builder.Obj`
* [PythonBuilder](https://cgarciae.github.io/phi/python_builder.m.html)
* `phi.builder.Builder.RegisterAt`
        """
        _return_type = None
        n -= 1

        if '_return_type' in kwargs:
            _return_type = kwargs['_return_type']
            del kwargs['_return_type']


        @utils.lift
        def g(x):
            new_args = args[0:n] + (x,) + args[n:] if n >= 0 else args
            return f(*new_args, **kwargs)

        return self.__then__(g, _return_type=_return_type)

    def Then0(self, f, *args, **kwargs):
        """
`Then0(f, ...)` is equivalent to `ThenAt(0, f, ...)`. Checkout `phi.builder.Builder.ThenAt` for more information.
        """
        return self.ThenAt(0, f, *args, **kwargs)

    def Then(self, f, *args, **kwargs):
        """
`Then(f, ...)` is equivalent to `ThenAt(1, f, ...)`. Checkout `phi.builder.Builder.ThenAt` for more information.
        """
        return self.ThenAt(1, f, *args, **kwargs)

    Then1 = Then

    def Then2(self, f, arg1, *args, **kwargs):
        """
`Then2(f, ...)` is equivalent to `ThenAt(2, f, ...)`. Checkout `phi.builder.Builder.ThenAt` for more information.
        """
        args = (arg1,) + args
        return self.ThenAt(2, f, *args, **kwargs)

    def Then3(self, f, arg1, arg2, *args, **kwargs):
        """
`Then3(f, ...)` is equivalent to `ThenAt(3, f, ...)`. Checkout `phi.builder.Builder.ThenAt` for more information.
        """
        args = (arg1, arg2) + args
        return self.ThenAt(3, f, *args, **kwargs)

    def Then4(self, f, arg1, arg2, arg3, *args, **kwargs):
        """
`Then4(f, ...)` is equivalent to `ThenAt(4, f, ...)`. Checkout `phi.builder.Builder.ThenAt` for more information.
        """
        args = (arg1, arg2, arg3) + args
        return self.ThenAt(4, f, *args, **kwargs)

    def Then5(self, f, arg1, arg2, arg3, arg4, *args, **kwargs):
        """
`Then5(f, ...)` is equivalent to `ThenAt(5, f, ...)`. Checkout `phi.builder.Builder.ThenAt` for more information.
        """
        args = (arg1, arg2, arg3, arg4) + args
        return self.ThenAt(5, f, *args, **kwargs)

    def Branch(self, *branches, **kwargs):
        """
While `Seq` is sequential, `Branch` allows you to split the computation and get back a list with the result of each path. While the list literal should be the most incarnation of this expresion, it can actually be any iterable (implements `__iter__`) that is not a tuple and yields a valid expresion.

The expression

    k = Branch(f, g)

is equivalent to

    k = lambda x: [ f(x), g(x) ]


In general, the following rules apply after compilation:

**General Branching**

    Branch(f0, f1, ..., fn)

is equivalent to

    lambda x: [ f0(x), f1(x), ..., fn(x) ]


**Composing & Branching**

It is interesting to see how braching interacts with composing. The expression

    Seq(f, Branch(g, h))

is *almost* equivalent to

    Branch( Seq(f, g), Seq(f, h) )

As you see its as if `f` where distributed over the Branch. We say *almost* because their implementation is different

    def _lambda(x):
        x = f(x)
        return [ g(x), h(x) ]

vs

    lambda x: [ g(f(x)), h(f(x)) ]

As you see `f` is only executed once in the first one. Both should yield the same result if `f` is a pure function.

### Examples

    form phi import P, Branch

    avg_word_length = P.Pipe(
        "1 22 333",
        lambda s: s.split(' '), # ['1', '22', '333']
        lambda l: map(len, l), # [1, 2, 3]
        Branch(
            sum # 1 + 2 + 3 == 6
        ,
            len # len([1, 2, 3]) == 3
        ),
        lambda l: l[0] / l[1] # sum / len == 6 / 3 == 2
    )

    assert avg_word_length == 2

The previous could also be done more briefly like this

    form phi import P, Obj, Branch

    avg_word_length = P.Pipe(
        "1 22 333", Obj
        .split(' ')  # ['1', '22', '333']
        .map(len)    # [1, 2, 3]
        .Branch(
            sum  #sum([1, 2, 3]) == 6
        ,
            len  #len([1, 2, 3]) == 3
        ),
        P[0] / P[1]  #6 / 3 == 2
    )

    assert avg_word_length == 2

In the example above the last expression

    P[0] / P[1]

works for a couple of reasons

1. The previous expression returns a list
2. In general the expression `P[x]` compiles to a function with the form `lambda obj: obj[x]`
3. The class `Lambda` (the class from which the object `P` inherits) overrides most operators to create functions easily. For example, the expression

    (P * 2) / (P + 1)

compile to a function of the form

    lambda x: (x * 2) / (x + 1)

Check out the documentatio for Phi [lambdas](https://cgarciae.github.io/phi/lambdas.m.html).

        """
        gs = [ _parse(code)._f for code in branches ]

        def h(x, state):
            ys = []
            for g in gs:
                y, state = g(x, state)
                ys.append(y)

            return (ys, state)

        return self.__then__(h, **kwargs)


    def Seq(self, *sequence, **kwargs):
        """
`Seq` is used to express function composition. The expression

    Seq(f, g)

be equivalent to

    lambda x: g(f(x))

As you see, its a little different from the mathematical definition. Excecution order flow from left to right, this makes reading and reasoning about code way more easy. This bahaviour is based upon the `|>` (pipe) operator found in languages like F#, Elixir and Elm. You can pack as many expressions as you like and they will be applied in order to the data that is passed through them when compiled an excecuted.

In general, the following rules apply for Seq:

**General Sequence**

    Seq(f0, f1, ..., fn-1, fn)

is equivalent to

    lambda x: fn(fn-1(...(f1(f0(x)))))

**Single Function**

    Seq(f)

is equivalent to

    f

**Identity**

The empty Seq

    Seq()

is equivalent to

    lambda x: x

### Examples

    from phi import P, Seq

    f = Seq(
        P * 2,
        P + 1,
        P ** 2
    )

    assert f(1) == 9 # ((1 * 2) + 1) ** 2

The previous example using `P.Pipe`

    from phi import P

    assert 9 == P.Pipe(
        1,
        P * 2,  #1 * 2 == 2
        P + 1,  #2 + 1 == 3
        P ** 2  #3 ** 2 == 9
    )
        """
        fs = [ _parse(elem)._f for elem in sequence ]

        def g(x, state):
            return functools.reduce(lambda args, f: f(*args), fs, (x, state))

        return self.__then__(g, **kwargs)

    @property
    def Rec(self):
        """
`Branch` provides you a way to branch the computation as a list, but access to the values of each branch are then done by index, this might be a little inconvenient because it reduces readability. `Rec` branches provide a way to create named branches via `Rec(**kwargs)` where the keys are the names of the branches and the values are valid expressions representing the computation of that branch.

A special object is returned by this expression when excecuted, this object derives from `dict` and fully emulates it so you can treat it as such, however it also implements the `__getattr__` method, this lets you access a value as if it where a field

### Examples

    from phi import P, Rec

    stats = P.Pipe(
        [1,2,3],
        Rec(
            sum = sum
        ,
            len = len
        )
    )

assert stats.sum == 6
assert stats.len == 3

assert stats['sum'] == 6
assert stats['len'] == 3

Now lets image that we want to find the average value of the list, we could calculate it outside of the pipe doing something like `avg = stats.sum / stats.len`, however we could also do it inside the pipe using `Rec` field access lambdas

    from phi import P, Rec

    avg = P.Pipe(
        [1,2,3],
        Rec(
            sum = sum   #6
        ,
            len = len   #3
        ),
        Rec.sum / Rec.len  #6 / 3 == 2
    )

    assert avg == 2
        """
        return _RecordProxy(self)

    def With(self, context_manager, *body, **kwargs):
        """
**With**

    def With(context_manager, *body):

**Arguments**

* **context_manager**: a [context manager](https://docs.python.org/2/reference/datamodel.html#context-managers) object or valid expression from the DSL that returns a context manager.
* ***body**: any valid expression of the DSL to be evaluated inside the context. `*body` is interpreted as a tuple so all expression contained are composed.

As with normal python programs you sometimes might want to create a context for a block of code. You normally give a [context manager](https://docs.python.org/2/reference/datamodel.html#context-managers) to the [with](https://docs.python.org/2/reference/compound_stmts.html#the-with-statement) statemente, in Phi you use `P.With` or `phi.With`

**Context**

Python's `with` statemente returns a context object through `as` keyword, in the DSL this object can be obtained using the `P.Context` method or the `phi.Context` function.

### Examples

    from phi import P, Obj, Context, With, Pipe

    text = Pipe(
        "text.txt",
        With( open, Context,
            Obj.read()
        )
    )

The previous is equivalent to

    with open("text.txt") as f:
        text = f.read()

        """
        context_f = _parse(context_manager, else_input=True)._f
        body_f = E.Seq(*body)._f

        def g(x, state):
            context, state = context_f(x, state)
            with context as scope:
                with _WithContextManager(scope):
                    return body_f(x, state)

        return self.__then__(g, **kwargs)


    @property
    def Read(self):
        """
Giving names and saving parts of your computation to use then latter is useful to say the least. In Phi the expressions

    Write('x')
    Write['x']
    Write.x

all behave just like the indentity except that they also creates a reference to that value which you can call latter. Here `x` is the name of the reference. To read the previous you would use any of the following expressions

    Read('x')
    Read['x']
    Read.x

This is equivalent to a sort of function like this

    lambda z: read('x')

where the input is totally ignored and a hypothetical `read` function is given the reference name and it should return its stored value (internally its not implemented like this).

** IMPORTANT **
`Read` and `Write` only work property inside a `phi.dsl.Expression.Seq` or `phi.dsl.Expression.Pipe` expression. This is done because `Ref`s need to be defined a specific context or else value might be leaked between different calls or even nested functions that might happen to be using Phi, therefore, Seq and Pipe a given the task to defined this context.

### Example
Lets see a common situation where you would use this

    from phi import P, Branch, Seq, Read, Write

    result = P.Pipe(
        input,
        f1, Write('ref')
        f2,
        Branch(
            f3
        ,
            Seq(
                Read('ref'),
                f4
            )
        )
    )

Here you *save* the value outputed by `fun_1` and the load it as the initial value of the second branch. In normal python the previous would be *almost* equivalent to

    x = f1(input)
    ref = x
    x = f2(x)

    result = [
        f3(x)
    ,
        f4(ref)
    ]
        """
        return _ReadProxy(self)

    @property
    def Write(self):
        """See `phi.dsl.Expression.Read`"""
        return _WriteProxy(self)

    @property
    def Rec(self):
        """
`Rec` is a `property` that returns an object that defines the `__getattr__` and `__getitem__` methods which when called help you create lambdas that emulates a field access. The following expression

    Rec.some_field

is equivalent to

    lambda rec: rec.some_field

**Examples**

    from phi import P, Obj, Rec

    class Point(object):

        def __init__(self, x, y):
            self.x = x
            self.y = y

        def flip_cords(self):
            y = self.y
            self.y = self.x
            self.x = y

    assert 4 == P.Pipe(
        Point(1, 2),         # point(x=1, y=2)
        Obj.flip_cords(),    # point(x=2, y=1)
        Rec.x,               # point.x = 2
        P * 2                # 2 * 2 = 4
    )

**Also see**

* `phi.builder.Builder.Obj`
* `phi.builder.Builder.Read`
* `phi.builder.Builder.Write`
        """
        return _RecordProxy(self)

    @property
    def Obj(self):
        """
`Obj` is a `property` that returns an object that defines the `__getattr__` method which when called helps you create a partial that emulates a method call. The following expression

    Obj.some_method(x1, x2, ...)

is equivalent to

    lambda obj: obj.some_method(x1, x2, ...)

**Examples**

    from phi import P, Obj

    assert "hello world" == P.Pipe(
        "  HELLO HELLO {0}     ",
        Obj.format("WORLD"),  # "   HELLO HELLO WORLD     "
        Obj.strip(),          # "HELLO HELLO WORLD"
        Obj.lower()           # "hello hello world"
        Obj.split(' ')        # ["hello", "hello", "world"]
        Obj.count("hello")    # 2
    )

**Also see**

* `phi.builder.Builder.Rec`
* [dsl.Write](https://cgarciae.github.io/phi/dsl.m.html#phi.dsl.Write)
* `phi.builder.Builder.Write`
        """
        return _ObjectProxy(self)

    Ref = Ref


    def Val(self, val, **kwargs):
        """
The expression

    Val(a)

is equivalent to the constant function

    lambda x: a

All expression in this module interprete values that are not functions as constant functions using `Val`, for example

    Seq(1, P + 1)

is equivalent to

    Seq(Val(1), P + 1)

The previous expression as a whole is a constant function since it will return `2` no matter what input you give it.
        """
        f = utils.lift(lambda z: val)

        return self.__then__(f, **kwargs)


    def If(self, condition, *then, **kwargs):
        """
**If**

    If(Predicate, *Then)

Having conditionals expressions a necesity in every language, Phi includes the `If` expression for such a purpose.

**Arguments**

* **Predicate** : a predicate expression uses to determine if the `Then` or `Else` branches should be used.
* ***Then** : an expression to be excecuted if the `Predicate` yields `True`, since this parameter is variadic you can stack expression and they will be interpreted as a tuple `phi.dsl.Seq`.

This class also includes the `Elif` and `Else` methods which let you write branched conditionals in sequence, however the following rules apply

* If no branch is entered the whole expression behaves like the identity
* `Elif` can only be used after an `If` or another `Elif` expression
* Many `Elif` expressions can be stacked sequentially
* `Else` can only be used after an `If` or `Elif` expression

** Examples **

    from phi import P, If

    assert "Between 2 and 10" == P.Pipe(
        5,
        If(P > 10,
            "Greater than 10"
        ).Elif(P < 2,
            "Less than 2"
        ).Else(
            "Between 2 and 10"
        )
    )
        """
        cond_f = _parse(condition)._f
        then_f = E.Seq(*then)._f
        else_f = utils.identity

        ast = (cond_f, then_f, else_f)

        g = _compile_if(ast)

        expr = self.__then__(g, **kwargs)
        expr._ast = ast
        expr._root = self

        return expr

    def Else(self, *Else, **kwargs):
        """See `phi.dsl.Expression.If`"""
        root = self._root
        ast = self._ast

        next_else = E.Seq(*Else)
        ast = _add_else(ast, next_else)

        g = _compile_if(ast)

        return root.__then__(g, **kwargs)
    #Else.__doc__ = If.__doc__

    def Elif(self, condition, *then, **kwargs):
        """See `phi.dsl.Expression.If`"""
        root = self._root
        ast = self._ast

        cond_f = _parse(condition)._f
        then_f = E.Seq(*then)._f
        else_f = utils.identity

        next_else = (cond_f, then_f, else_f)
        ast = _add_else(ast, next_else)

        g = _compile_if(ast)

        expr = root.__then__(g, **kwargs)
        expr._ast = ast
        expr._root = root

        return expr

    #Elif.__doc__ = If.__doc__


    @staticmethod
    def Context(*args):
        """
**Builder Core**. Also available as a global function as `phi.Context`.

Returns the context object of the current `dsl.With` statemente.

**Arguments**

* ***args**: By design `Context` accepts any number of arguments and completely ignores them.

This is a classmethod and it doesnt return a `Builder`/`Lambda` by design so it can be called directly:

    from phi import P, Context, Obj

    def read_file(z):
        f = Context()
        return f.read()

    lines = P.Pipe(
        "text.txt",
        P.With( open,
            read_file,
            Obj.split("\\n")
        )
    )

Here we called `Context` with no arguments to get the context back, however, since you can also give this function an argument (which it will ignore) it can be passed to the DSL so we can rewrite the previous as:

    from phi import P, Context, Obj

    lines = P.Pipe(
        "text.txt",
        P.With( open,
            Context, # f
            Obj.read()
            Obj.split("\\n")
        )
    )

`Context` yields an exception when used outside of a `With` block.

**Also see**

* `phi.builder.Builder.Obj`
* [dsl](https://cgarciae.github.io/phi/dsl.m.html)
        """
        if _WithContextManager.WITH_GLOBAL_CONTEXT is utils.NO_VALUE:
            raise Exception("Cannot use 'Context' outside of a 'With' block")

        return _WithContextManager.WITH_GLOBAL_CONTEXT

E = Expression()

def _add_else(ast, next_else):

    if hasattr(ast, "__call__"):
        return next_else

    cond, then, Else = ast

    return (cond, then, _add_else(Else, next_else))



def _compile_if(ast):
    if hasattr(ast, "__call__"):
        return ast

    cond, then, Else = ast

    Else = _compile_if(Else)

    return lambda x: then(x) if cond(x) else Else(x)

#######################
### FUNCTIONS
#######################


def _parse(code, else_input=False):
    #if type(code) is tuple:
    if isinstance(code, Expression):
        return code
    elif hasattr(code, '__call__') or isclass(code):
        return Expression(utils.lift(code))
    else:
        return E.Val(code)
