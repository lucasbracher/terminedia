from enum import Enum, IntFlag

from terminedia.utils import mirror_dict, V2, NamedV2


#: Constant used as color to mean the default terminal foreground
#: (Currently all other color values should be RGB)
DEFAULT_FG = 0xffff
#: Constant used as color to mean the default terminal background
DEFAULT_BG = 0xfffe
#: Constant used as color to mean keep the current context colors
CONTEXT_COLORS = 0xfffd
#: Constant to mean keep the current value, usd as char, fg, bg or effect
TRANSPARENT = 0xfffc
#: Special value to mean no transformation to a given channel
#: on context-transforms. (See `terminedia.utils.create_transformer`)
NOP = "NOP"
#: Special value used in character data maps to indicate
#: the cell continues a double width character to the left
CONTINUATION = "CONT"

#: Character to denote an empty-space on images and drawing contexts
EMPTY = "\x20"
#: Character to denote a filled-pixel on images and drawing contexts
FULL_BLOCK = '\u2588'

class Directions:
    """Direction vector constants.

    These are used directly as text-printing direction on
    a :any:`Screen` context, and are free to general use
    in user applications
    """
    UP = NamedV2(0, -1)
    RIGHT = NamedV2(1, 0)
    DOWN = NamedV2(0, 1)
    LEFT = NamedV2(-1, 0)


class Effects(IntFlag):
    """Text effect Enums

    Some of these are implemented in most terminal programs -
    the codes used here are so that their value can be ORed.
    (The "real" codes for terminal rendering are issed
    in ``terminal.py``).

    The somewhat arbitrary order tries to put first
    the most supported/most useful attributes.
    """
    def __iter__(self):
        """much hacky. very smart: composed flags are now iterable!"""
        for element in self.__class__:
            if self & element:
                yield element

    none = 0
    bold = 1
    italic = 2
    underline = 4
    reverse = 8
    blink = 16
    faint = 32
    fast_blink = 64
    conceal = 128
    crossed_out = 256
    double_underline = 512
    framed = 1024
    encircled = 2048
    overlined = 4096
    fraktur = 8192
    squared = 16384
    negative_squared = 32768
    negative_circled = 65536
    parenthesized = 2 ** 17
    fullwidth = 2 ** 18
    math_bold = 2 ** 19
    math_bold_italic = 2 ** 20
    super_bold = 2 ** 21
    super_script = 2 ** 22


# Effects that are rendered by character translation / unicode combining
# rather than by ANSI terminal sequences
unicode_effects = {
    Effects.encircled, Effects.squared, Effects.negative_squared,
    Effects.negative_circled, Effects.parenthesized, Effects.fullwidth,
    Effects.math_bold, Effects.math_bold_italic, Effects.super_bold,
    Effects.super_script
}
UNICODE_EFFECTS = Effects(sum(effect for effect in Effects if effect in unicode_effects))

# (encircled is actually defined as an ANSI effect, but no terminal
# support for it was found at encoding time.)


ESC = "\x1b"

