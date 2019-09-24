def mirror_dict(dct):
    """Creates a new dictionary exchanging values for keys
    Args:
      - dct (mapping): Dictionary to be inverted
    """
    return {value: key for key, value in dct.items()}


class V2(tuple):
    """2-component Vector class to ease drawing

    Works as a 2-sequence, but offers "x" and "y" properties to the coordinates
    as well as basic operations. As V2 inherits from Python's tuple, it is imutable
    and can be used as dictionary keys, among other common sequence operations.

    Args:
      x (number or 2-sequence): 1st vector coordinate or 2-sequence with coordinates
      y (number): 2nd vector coordinate. Ignored if x is a sequence
    Suported ops:
      - + (``__add__``): Adds both components of 2 vectors
      - - (``__sub__``): Subtracts both components of 2 vectors.
      - * (``__mul__``): Multiplies vector components by a scalar
      - abs (``__abs__``): Returns vector length
    """

    def __new__(cls, x=0, y=0):
        """Accepts two coordinates as two parameters for x and y"""
        # Enable working with values defined in Enums
        if hasattr(x, "value"):
            x = x.value
        if hasattr(x, "__len__"):
            x, y = x
        return super().__new__(cls, (x, y))

    def __init__(self, *args, **kw):
        # "Eat" subclass arguments that would
        # otherwise hit tuple.__init__ and
        # cause a fault.
        return
        # If composition of this class ever gets more complex, uncomment the
        # pedantic way to go is:

        #x, y = kw.pop(x, None), kw.pop(y, None)
        #if not x and not y and len(args) >= 2:
            #args = args[2:]
        #super().__init__(*args, **kw)

    x = property(lambda self: self[0])
    y = property(lambda self: self[1])

    def __add__(self, other):
        """Adds both components of a V2 or other 2-sequence"""
        return self.__class__(self[0] + other[0], self[1] + other[1])

    def __sub__(self, other):
        """Subtracts both components of a V2 or other 2-sequence"""
        return self.__class__(self[0] - other[0], self[1] - other[1])

    def __mul__(self, other):
        """multiplies a V2 by an scalar"""
        return self.__class__(self[0] * other, self[1] * other)

    def __abs__(self):
        """Returns Vector length
           Returns:
             - (float): Euclidian length of vector

        """
        return (self.x ** 2 + self.y ** 2) ** 0.5

    @property
    def as_int(self):
        return self.__class__(int(self.x), int(self.y))

    def __repr__(self):
        return f"V2({self.x}, {self.y})"


class NamedV2(V2):
    """Vector meant to be used as constant, with a string-repr name"""

    def __init__(self, *args, name=None, **kw):
        """Optional name - if used as a descriptor, name is auto-set"""
        self.name = name
        super().__init__(*args, **kw)

    def __set_name__(self, owner, name):
        self.owner_name = owner.__name__
        self.name = name

    def __get__(self, instance, owner):
        return self

    def __repr__(self):
        return f"{self.owner_name}.{self.name}"

    def __str__(self):
        return self.name

    # Force operator methods to get these values as pure V2 instances
    # (so that adding "Directions" results in a normal vector,
    # not an object with a __dict__)
    for method in "__add__ __sub__ __mul__ __abs__ as_int".split():
        locals()[method] = (lambda method: lambda s, *args: getattr(V2, method)(V2(s), *args))(method)

    @property
    def value(self):
        """Returns self, keeping compatibility with Python Enums if used as a descriptor"""
        return self

class Color:
    # TODO: a context sensitive color class
    # (to stop yielding constant values to be used as RGB tripplets)
    pass


class LazyBindProperty:
    def __init__(self, initializer):
        self.initializer = initializer

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if not instance:
            return self
        if not self.name in instance.__dict__:
            instance.__dict__[self.name] = self.initializer(instance)
        return instance.__dict__[self.name]


def init_context_for_thread(context, char=None, color=None, background=None, effects=None, direction=None):
    """Create all expected data inside a context in the current thread.

    Multi-threaded apps should call this to update a Screen or Shape instance
    before trying to use that instance in a different thread than its originating one.
    """
    from terminedia.values import DEFAULT_BG, DEFAULT_FG, BlockChars, Directions, Effects
    context.char = char or BlockChars.FULL_BLOCK
    context.color = color or DEFAULT_FG
    context.background = background or DEFAULT_BG
    context.effects = effects or Effects.none
    context.direction = direction or Directions.RIGHT
    context.transformer = None


def create_transformer(context, slots, clear=False):
    """Attach a specialized callable to a drawing context to transform pixel values during rendering

    Args:
      - context (Drawing context namespace): the context
      - slots (Optional[Union[Constant, Callable[pos, values, context]]]): a sequence of callables that will perform the transform on each channel.
      - clear (bool): if True will replace existing transformers.
                      if False, the new transformation will be appended to the existing transformations in
                      the context.

      The callables passed to "slots" receive the full Pixel values as a sequence
      (for full capability pixels: char, foreground, background, text effects).
      Each callable have to return the final constant that will be applied as
      that component on the drawing target data.

      If one member of "slots" is not callable, it self is used
      as a constant for that channel. The special value `NOP`
      (``terminedia.values.NOP`` means no change to that channel.)

      Slot callables can return the special  `TRANSPARENT` constant to
      indicate the target value at the corresponding plane is preserved.

      Having fewer slots than are planes in the drawing context, means the
      remaining planes are left empty.

      ex. to install a transformer to force all text effects off:
      ```
      from terminedia values import create_transformer, NOP, Effects
      ...
      create_transformer(shape.context, [NOP, NOP, NOP, Effects.none])
      ```

      For a transformer that will force all color rendering
      to be done to the background instead of foreground:
      ```
      create_transformer(shape.context, [NOP, TRANSPARENT, lambda pos, values, context: values[1], NOP])
      ```

      Transfomer to make all printed numbers be printed blinking:

      ```
      create_transformer(shape.context, [NOP, NOP, NOP, lambda pos, values, context: Effects.blink if values[0].isdigit() else TRANSPARENT])
      ```

      To uninstall a transformer, just set it to `None`
      (that is: `shape.context.transformer = None`) or call this with slots=None.

      # TODO -make transformer into a class that allows post-creation introspection and manipulation

    """
    from terminedia.values import NOP

    if not slots:
        context.transformer = None
        return

    previous_transformer = getattr(context, "transformer", None)
    if clear:
        previous_transformer = None

    def transformer(pos, values):
        if previous_transformer:
            values = previous_transformer(pos, values)
        return [
            slot(pos, values, context) if callable(slot) else
            slot if slot is not NOP else
            values[i]
                for i, slot in enumerate(slots)
        ]
    context.transformer = transformer
