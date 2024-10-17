# digitgrouper

This is a do-over of my hacking around with
[numderline](https://github.com/trishume/numderline), using
[fontforge][]'s built-in rule generation rather than trying to work
via a feature file, which causes fontforge to
[crash](https://github.com/fontforge/fontforge/issues/2881).  It also
uses GPOS rules rather than building new glyphs at different positions
and switching them in via GSUB (though new glyphs would be required for
the shrink feature anyway -- just not as many).

There's some additional verbiage about this effort [over
here](https://www.xn--tkuka-m3a3v.dev/thousand-separators-in-font/), for whatever that's worth.

## Usage
```
digitgrouper.py [-h] [--monospace] [--terminal] [--final-rules]
                [--gap-size GAP_SIZE] [--shrink_x SHRINK_X]
                [--shrink_y SHRINK_Y] [--separate-files]
                font [font ...]
```

`--monospace`
: When inserting the digit-grouping separators, keep the same spacing as
  the number would have had without those insertions.  This is necessary
  to maintain the expected layout in monospaced type.  Digits are pinched
  together slightly to make extra room where needed.
: This may look a bit rough, and might need some extra tinkering with
  other settings to get it to look right and to work well with some
  softare.

`--terminal`
: Don't try to emit `GPOS` rules.  Make a whole bunch of extra glyphs at
  different positions instead.  This is only meaningful in `--monospace`
  situations, but is necessary when the font will be used by something
  which caches rendered glyphs without regard to the contextual `GPOS`
  edits.

`--final-rules`
: By default the new font rules are inserted before pre-existing rules.
  Some of the changes this causes might interfere with those existing
  rules (stylistic sets, etc.).  With this switch try putting them at the
  end, instead.  This can cause a permutation explosion of glyph
  modifications to account for the substitutions that might have happened,
  but it's more likely to work properly.

`--always-on`
: By default grouping needs to be enabled via font features like `dgsp`.
  This enables it under the `calt` feature, which is default-on.

`--gap-size=GAP_SIZE`
: Fiddle with the size of the separator.  By default it tries to
  duplicate the width of a thin space, or a comma, or a third of the width
  of a zero.  Whatever it finds first.  The units vary by font file, so
  just fiddle with it until it looks right.


[fontforge]: <https://fontforge.org/>
