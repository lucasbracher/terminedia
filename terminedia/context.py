"""Painting context related classes and utility funcions
"""
import threading
from copy import copy
from types import FunctionType

from terminedia.utils import Color, V2
from terminedia.subpixels import BlockChars
from terminedia.values import DEFAULT_BG, DEFAULT_FG, Directions, Effects



_sentinel = object()


class Transformer:
    pass


class ContextVar:
    def __init__(self, type, default=None):
        self.type = type
        self.default = default

    def __set_name__(self, owner, name):
        self.name = name

    def __set__(self, instance, value):
        if not isinstance(value, self.type):
            # May generate ValueError TypeError: expected behavior
            type = self.type[0] if isinstance(self.type, tuple) else self.type
            value = type(value)
        setattr(instance._locals, self.name, value)

    def __get__(self, instance, owner):
        if not instance:
            return self
        value = getattr(instance._locals, self.name, _sentinel)
        if value is _sentinel:
            value=self.default
            if callable(value):
                value = value()
            setattr(instance._locals, self.name, value)
        return value


class Context:
    """Context class for Screen and Shape objects. Instances should live as ".context" on those

        Args:
        - **kw: initial keyword arguments for a context

        The drawing and printing operations on terminedia will
        set a graphic element on a target. Depending on the
        function it will either write an arbitrary character
        or just set/reset a pixel in the desired color.

        All the other attributes for the element being drawn are picked from
        its ".context" attribute which is an instance of this.

        The attributes here are set independently for each thread,
        and these are the ones currently used by the drawing functions:

        - color: color special value or RGB sequence for foreground color - either int 0-255  or float 0-1 based.
        - background: color special value or RGB sequence sequence for background color
        - direction: terminedia.Directions Enum value with writting direction
        - effects: terminedia.Effects Enum value with combination of text effects
        - char: Char to be plotted when setting a single color.
        - transformer: Callback that will change in-place each attribute of
        a graphic element immediately before actually setting then on the target.

        Also, if used as a context-manager, this pushes all current attributes in a stack,
        providing a practical way for a sub-routine to draw things
        to the target without messing with the callee's expected drawing context.
        Otherwise one would have to manually save and restore
        the context colors for each operation.  When entering
        a Context as a context manager, the original attributes are
        retained, but any changes to it in the corresponding `with` block
        are reverted on `__exit__`.
    """

    char = ContextVar(str, BlockChars.FULL_BLOCK)
    color = ContextVar((tuple, Color, int), DEFAULT_FG)
    background = ContextVar((tuple, Color, int), DEFAULT_BG)
    effects = ContextVar(Effects, Effects.none)
    direction = ContextVar(V2, Directions.RIGHT)
    transformer = ContextVar((Transformer, FunctionType, type(None)), None)
    font = ContextVar(str, "")

    def __init__(self, **kw):
        self._locals = threading.local()
        self._update(kw)

    def _update(self, params):
        for attr, value in params.items():
            setattr(self, attr, value)

    def __setattr__(self, name, value):
        if name.startswith("_") or getattr(self.__class__, name, None):
            super().__setattr__(name, value)
        else:
            setattr(self._locals, name, value)

    def __getattr__(self, name):
        return getattr(self._locals, name)

    def __call__(self, **kw):
        """Update new parameters before Context is used as a context manager"""
        self._locals._new_parameters = kw
        return self

    def __enter__(self):
        new_parameters = self._locals.__dict__.pop("_new_parameters", {})
        data = copy(self._locals.__dict__)
        self._locals.__dict__.setdefault("_stack", []).append(data)
        self._update(new_parameters)
        return self

    def __exit__(self, exc_name, traceback, frame):
        data = self._locals._stack.pop()
        self._update(data)

    def __repr__(self):
        return "Context[\n{}\n]".format("\n".join(
            f"   {key} = {getattr(self._locals, key)!r}" for key in dir(self._locals)
            if not key.startswith("_")
        ))
