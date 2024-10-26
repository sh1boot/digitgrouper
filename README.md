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
digitgrouper.py [-h] [-o [filename]] [--monospace] [--terminal]
                [--before] [--always-on [feature]] [--huddle]
                [--gap-size GAP_SIZE] [--rename [suffix]] [--no-rename]
                filename [filename ...]
```

`--output`
Output filename.  If it ends with .ttc then a single font collection
file will be written.  Otherwise if it contains a %-format string then
each output file will be named either by the font's name (%s) or a
sequence number starting with zero.

`--monospace`
When inserting the digit-grouping separators, keep the same spacing as
the number would have had without those insertions.  This is necessary
to maintain the expected layout in monospaced type.  Digits are pinched
together slightly to make extra room where needed.

This may look a bit rough, and might need some extra tinkering with
other settings to get it to look right and to work well with some
softare.

`--terminal`
Don't try to emit `GPOS` rules.  Make a whole bunch of extra glyphs at
different positions instead.  This option implies `--monospace` and is
necessary when the font will be used by something which caches
rendered glyphs without regard to the contextual `GPOS` edits.

`--before`
By default the new font rules are inserted after pre-existing rules
(stylistic sets, etc.), so as to avoid interfering with them.  This
can result in a permutation explosion of glyphs, or may cause other
problems.  Try this to see if it inserting the new rules first works
better.

`--always-on`
choose a feature (`dgsp`, `dgap`, `dgco`, etc.) to force on by
default, rather than needing to configure the font externally.

`--huddle`
Squeeze the grouped digits together symmetrically, to try to avoid
moving them too far and causing clipping in some terminals.  This can
cause irregular alignment in the surrounding thousand separators.

`--gap-size`
Fiddle with the size of the separator.  By default it tries to
duplicate the width of a thin space, or a comma, or a third of the width
of a zero.  Whatever it finds first.  The units vary by font file, so
just fiddle with it until it looks right.

`--no-rename`
Don't modify the font name.

`--rename`
Modify the font name by adding `DG` (or the specified suffix) to the
end of the first word.


## other things to try

[FontTools] has some commands to optimise tables and merge fonts.  Maybe
they'll have some positive impact on the output:

`fonttools otlLib.optimize input.ttf -o output.ttf`

`fonttools ttLib in1.ttf in2.ttf in3.ttf -o output.ttc`

[FontTools]: <https://github.com/fonttools/fonttools>
[FontForge]: <https://fontforge.org/>
