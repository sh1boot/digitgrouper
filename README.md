# digitgrouper

This is a do-over of my hacking around with
[numderline](https://github.com/trishume/numderline), using
[fontforge][]'s built-in rule generation rather than trying to work
via a feature file, which causes fontforge to
[crash](https://github.com/fontforge/fontforge/issues/2881).  It also
uses GSUB rules rather than building new glyphs at different positions
(though new glyphs would be required for the shrink feature anyway --
just not as many).

There's some additional verbiage about this effort [over
here](https://www.xn--tkuka-m3a3v.dev/thousand-separators-in-font/), for whatever that's worth.

[fontforge]: <https://fontforge.org/>
