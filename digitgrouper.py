#!/usr/bin/env python3
import argparse
import contextlib
import re

import fontforge
import psMat

DECIMAL_LIST = '0123456789'
HEXADECIMAL_LIST = '0123456789abcdefABCDEF'

SCRIPTS = (
    ('DFLT',('dflt')),
    ('latn',('dflt')),
    ('cyrl',('dflt')),
    ('grek',('dflt')),
    ('kana',('dflt'))
)
MAIN_FEATURE = ('dgsp', SCRIPTS)
COMMA_FEATURE = ('dgco', SCRIPTS)
APSTR_FEATURE = ('dgap', SCRIPTS)
DOT_FEATURE = ('dgdo', SCRIPTS)
ALWAYS_ON_FEATURE = ('calt', SCRIPTS)
ALL_MODES = (MAIN_FEATURE, COMMA_FEATURE, APSTR_FEATURE, DOT_FEATURE)
HEXADECIMAL_MODE = (('dghx', SCRIPTS),)
DECIMAL_COMMA_MODE = (('dgdc', SCRIPTS),)

class Features:
    ALL = 'all'
    SPACE = 'space'
    COMMA = 'comma'
    APOSTROPHE = 'apostrophe'
    DOT = 'dot'
    HEXADECIMAL = 'hexadecimal'
    DECIMAL_COMMA = 'decimal-comma'
    ALWAYS = 'always'
    _MAP = {
        ALL: {'dgsp', 'dgco', 'dgap', 'dgdo', 'dghx'},
        SPACE: {'dgsp'},
        COMMA: {'dgco'},
        APOSTROPHE: {'dgap'},
        DOT: {'dgdo'},
        HEXADECIMAL: {'dghx'},
        DECIMAL_COMMA: {'dgdc'},
        ALWAYS: {'calt'},
    }
    @classmethod
    def get(cls, which):
        if which is None:
            return tuple(tuple())
        return tuple( (fourcc, SCRIPTS) for fourcc in cls._MAP[which] )

    @classmethod
    def make_always(cls, fourcc):
        for v in cls._MAP.values():
            if fourcc in v:
                v.update(cls._MAP[cls.ALWAYS])

def collect_equivalents(font, basis='0123456789', use_gsubs=False):
    result = set()
    for c in basis:
        glyph = font[ord(c)]
        name = glyph.glyphname
        result.add(name)
        if use_gsubs:
            additions = set()
            for sub in glyph.getPosSub('*'):
                if sub[1] in { 'Substitution', 'AltSubs', 'MultSubs' }:
                    additions |= set(sub[2:])
            # TODO: should recurse, maybe...
            result |= additions
    return result


def find_first(font, chars):
    for c in chars:
        if ord(c) in font:
            return font[ord(c)]
    return None


def find_gap_size(font, gap_size):
    with contextlib.suppress(ValueError):
        result = int(gap_size)
        if result > 0:
            return result

    glyph = find_first(font, gap_size if gap_size else '\N{THIN SPACE},. ')
    if glyph:
        gap_size = glyph.width

    # if suggested gap size is the size of a 0 it's probably
    # a monospaced font, so use the default monospace gap.
    size_of_0 = font[ord('0')].width
    if gap_size > size_of_0 // 2:
        gap_size = size_of_0 // 3
    return gap_size


def new_glyph(font, name, source=None, hshift=None):
    glyph = font.createChar(-1, name)
    if source:
        if hshift:
            glyph.addReference(source, psMat.translate(hshift, 0))
        else:
            glyph.addReference(source)
            glyph.left_side_bearing = int(font[source].left_side_bearing)
            glyph.right_side_bearing = int(font[source].right_side_bearing)
        glyph.width = int(font[source].width)
    return glyph

def resize_glyph(font, name, width, cls=None):
    glyph = font[name]
    change = int(glyph.width) - width
    glyph.left_side_bearing = int(glyph.left_side_bearing) - change // 2
    glyph.width = width
    if cls:
        glyph.glyphclass = cls


def slide_glyph(font, name, distance):
    glyph = font[name]
    glyph.left_side_bearing = int(glyph.left_side_bearing) + distance


def rename_font(font, suffix='DG'):
    oldname = font.familyname
    while oldname not in font.fontname and ' ' in oldname:
        # Sometimes things get tangled into the font name that don't belong
        # there.  Hopefully this can strip those off.
        oldname = oldname.rsplit(' ', 1)[0]
    newname = oldname + suffix
    font.familyname = font.familyname.replace(oldname, newname)
    font.fullname = font.fullname.replace(oldname, newname)
    font.fontname = font.fontname.replace(oldname, newname)
    for t in font.sfnt_names:
        if oldname in t[2] and newname not in t[2]:
            font.appendSFNTName(t[0], t[1], t[2].replace(oldname, newname))


def patch_a_font(font, monospace, terminal, before, gap_size, huddle):
    font.encoding = 'ISO10646'

    if terminal:
        monospace = True

    gap_size = find_gap_size(font, gap_size)
    print(f'zero: {font[ord("0")].width}, gap_size: {gap_size}')

    new_glyph(font, 'thsp.capture3', 'z')
    new_glyph(font, 'thsp.capture4', 'y')
    new_glyph(font, 'thsp.capture5', 'x')
    new_glyph(font, 'thsp.avoid', 'v')

    for d in [3,4,5]:
        space = find_first(font, '\N{THIN SPACE} ').glyphname
        comma = find_first(font, ',').glyphname
        apostrophe = find_first(font, "'").glyphname
        dot = find_first(font, '.').glyphname
        new_glyph(font, f'thsp.sep{d}', space)
        new_glyph(font, f'thsp.comma{d}', comma)
        new_glyph(font, f'thsp.apostrophe{d}', apostrophe)
        new_glyph(font, f'thsp.dot{d}', dot)

    dec_group = collect_equivalents(font, '0123456789', not before)
    hex_group = dec_group | collect_equivalents(font, 'abcdefABCDEF', not before)
    dsep_group = collect_equivalents(font, '.,', not before)
    capture_group = ['thsp.capture3','thsp.capture4','thsp.capture5','thsp.avoid']
    separator_group = set()
    for d in [3,4,5]:
        separator_group |= {f'thsp.sep{d}',f'thsp.comma{d}',f'thsp.apostrophe{d}',f'thsp.dot{d}'}

    for gn in separator_group:
        if monospace:
            adjustment = -gap_size if gn.endswith('5') else gap_size
            slide_glyph(font, gn, adjustment)
            resize_glyph(font, gn, 0, 'mark')
        else:
            resize_glyph(font, gn, gap_size)

    #print(f'decimals: {dec_group}')
    #print(f'hexadecimals: {hex_group}')

    adjustments = {
        'lf_1_6': -1 * (gap_size // 6),
        'rt_1_6':  1 * (gap_size // 6),
        'lf_1_4': -1 * (gap_size // 4),
        'rt_1_4':  1 * (gap_size // 4),
        'lf_1_2': -1 * (gap_size // 2),
        'rt_1_2':  1 * (gap_size // 2),
        'lf_3_4': -3 * (gap_size // 4),
        'rt_1_3':  1 * (gap_size // 3),
        'rt_2_3':  2 * (gap_size // 3),
        'lf_1_1': -1 * (gap_size // 1),
        'rt_1_1':  1 * (gap_size // 1),
    }

    classes = {
        'dec': dec_group,
        'hex': hex_group,
        'sep3': ['thsp.sep3'],
        'sep4': ['thsp.sep4'],
        'sep5': ['thsp.sep5'],
        'anysep3': ['thsp.sep3','thsp.comma3','thsp.apostrophe3','thsp.dot3'],
        'anysep4': ['thsp.sep4','thsp.comma4','thsp.apostrophe4','thsp.dot4'],
        'anysep5': ['thsp.sep5','thsp.comma5','thsp.apostrophe5','thsp.dot5'],
        'cap3': ['thsp.capture3'],
        'cap4': ['thsp.capture4'],
        'cap5': ['thsp.capture5'],
        'avoid': ['thsp.avoid'],
        'anycap': capture_group,
        'zero': collect_equivalents(font, '0', not before),
        'xx': collect_equivalents(font, 'bBoOxX', not before),
        'dot': collect_equivalents(font, '.', not before),
        'comma': collect_equivalents(font, ',', not before),
        'dotsep5': dsep_group | {'thsp.sep5','thsp.comma5','thsp.apostrophe5','thsp.dot5'},
    }
    for name in adjustments:
        classes['hex_'+name] = classes['hex']
        classes['dec_'+name] = classes['dec']
        if terminal:
            classes['hex_'+name] = [ v+'.'+name for v in classes['hex'] ]
            classes['dec_'+name] = [ v+'.'+name for v in classes['dec'] ]
    classes_fmt = {
        k: '[ ' + ' '.join(v) + ' ]' for k,v in classes.items()
    }

    curr_lookup = None
    subtable_index = 0

    if not before and font.gsub_lookups:
        curr_lookup = font.gsub_lookups[-1]

    def new_lookup(name, lu_type, which=Features.ALL):
        features = Features.get(which)
        nonlocal curr_lookup, subtable_index
        if curr_lookup:
            font.addLookup(name, lu_type, None, features, curr_lookup)
        else:
            font.addLookup(name, lu_type, None, features)
        curr_lookup = name
        subtable_index = 0

    def new_glyph_rule(name, lu_type, which=None):
        new_lookup(name, lu_type, which)
        font.addLookupSubtable(name, name)
        return name


    def new_ctx_subtable(st_type, rule):
        nonlocal curr_lookup, subtable_index, classes_fmt
        name = f'{curr_lookup}-{subtable_index}'
        if subtable_index:
            previous = f'{curr_lookup}-{subtable_index-1}'
            font.addContextualSubtable(curr_lookup, name, st_type,
                    rule.format(**classes_fmt), afterSubtable=previous)
        else:
            font.addContextualSubtable(curr_lookup, name, st_type,
                    rule.format(**classes_fmt))
        subtable_index += 1
        return name

    def new_coverage(rule):
        return new_ctx_subtable('coverage', rule)

    def new_rev_coverage(rule):
        return new_ctx_subtable('reversecoverage', rule)

    # Each lookup is executed in the order they're listed below, but
    # selectively enabled by their assigned font features.  Within each lookup,
    # the first matching subtable ends the search and advances to the next
    # character in the string.
    #
    # What are called 'glyph rules' here are substitutions which are described
    # within the glyph rather than within context rules.  The lookup and
    # subtable are given the same name so they can be used interchangeably
    # (glyphs reference the subtable, and subtable rules reference the lookup).
    #
    # Broadly, each group of digits is classified by its prefix, in left-to-
    # right order, and that classification is stretched out to the end of the
    # group of digits.  Then rules for whole numbers are applied in right-to-
    # left order to form groups of three or four digits depending on the
    # capture type, and a rule for decimals is applied in left-to-right order
    # to form groups of five digits.  Finally another rule sweeps away the
    # classification markers.
    #
    # After that a couple of extra tweaks are applied to use different
    # characters for the thousand separators if needed.

    # Rules to mark any digit in a string
    new_glyph_rule('capture_3digit', 'gsub_multiple')
    new_glyph_rule('capture_4digit', 'gsub_multiple')
    new_glyph_rule('capture_5digit', 'gsub_multiple')
    new_glyph_rule('capture_avoid', 'gsub_multiple')
    # And a rule to remove those marks
    new_glyph_rule('release_digit', 'gsub_ligature')
    new_glyph_rule('nop', 'gsub_single')
    for g in hex_group:
        # Arguments for gsub_multiple and gsub_ligature rules look the same,
        # but they have opposing substitution rules.
        font[g].addPosSub('capture_3digit', (g, 'thsp.capture3'))
        font[g].addPosSub('capture_4digit', (g, 'thsp.capture4'))
        font[g].addPosSub('capture_5digit', (g, 'thsp.capture5'))
        font[g].addPosSub('capture_avoid', (g, 'thsp.avoid'))
        for cap in capture_group:
            font[g].addPosSub('release_digit', (g, cap))

    # A rule to insert separator over capture.
    new_glyph_rule('insert_separator', 'gsub_single')
    font['thsp.capture3'].addPosSub('insert_separator', 'thsp.sep3')
    font['thsp.capture4'].addPosSub('insert_separator', 'thsp.sep4')
    font['thsp.capture5'].addPosSub('insert_separator', 'thsp.sep5')

    # Capture hexadecimal generously if cofigured to do so
    new_lookup('capture_as_hex', 'gsub_contextchain', Features.HEXADECIMAL)
    new_coverage('{hex} | {hex} @<capture_4digit> | {hex} {hex} {hex}')

    new_lookup('comma_as_decimal', 'gsub_contextchain', Features.DECIMAL_COMMA)
    # if it's `n,nnnn` that's a decimal number
    new_coverage( '{dec} {comma} | {dec} @<capture_5digit> | {dec} {dec} {dec} {dec}')
    new_coverage('{cap3} {comma} | {dec} @<capture_5digit> | {dec} {dec} {dec} {dec}')
    # otherwise if it's `,nnnnn` it's not clear what it is, so avoid it.
    new_coverage(       '{comma} | {dec} @<capture_avoid> | {dec} {dec} {dec}')
    # and we switch off support for decimal dot, while we're here.
    new_coverage(  '{cap3} {dot} | {dec} @<capture_avoid> | {dec} {dec} {dec}')
    new_coverage(   '{dec} {dot} | {dec} @<capture_avoid> | {dec} {dec} {dec}')

    # Captures for all the different digit types
    new_lookup('capture_numbers', 'gsub_contextchain')

    # if it's `..nnnnn`, that's probably an integer following a range.
    new_coverage( '{dot} {dot} | {dec} @<capture_3digit> | {dec} {dec} {dec} {dec}')
    # if it's `n.nnnn` that's a decimal number
    new_coverage( '{dec} {dot} | {dec} @<capture_5digit> | {dec} {dec} {dec} {dec}')
    new_coverage('{cap3} {dot} | {dec} @<capture_5digit> | {dec} {dec} {dec} {dec}')
    # otherwise if it's `.nnnnn` it's not clear what it is, so avoid it.
    new_coverage(       '{dot} | {dec} @<capture_avoid> | {dec} {dec} {dec}')

    ## TODO: consider: excluding `x` in middle of number (is it `XXXxYYY`?)
    # This is already partially-implemented in that the capture will break the
    # `0x` match.
    ## TODO: consider: excluding `#xxxxxx[^x]` because that's a colour code, or
    # break it into bytes.
    ## TODO: consider `'hxxx` for Verilog, `16#xxx` for VHDL, sh, Ada, etc..
    new_coverage( '{zero} {xx} | {hex} @<capture_4digit> | {hex} {hex} {hex} {hex}')
    new_coverage(       '{dec} | {dec} @<capture_3digit> | {dec} {dec} {dec}')

    # avoid doubling up on captures (can happen when using extra features)...
    new_coverage('{anycap} | {hex} @<nop> | {anycap}')
    # and then fill everything following a capture to match that type
    new_coverage('{cap3} | {dec} @<capture_3digit> |')
    new_coverage('{cap4} | {hex} @<capture_4digit> |')
    new_coverage('{cap5} | {dec} @<capture_5digit> |')
    new_coverage('{avoid} | {hex} @<capture_avoid> |')

    # Convert every nth capture into a digit group
    new_lookup('reflow_numbers_rev', 'gsub_reversecchain')
    new_rev_coverage('| {cap3} => {sep3} | {dec} {cap3} {dec} {cap3} {dec}')
    new_rev_coverage('| {cap4} => {sep4} | {hex} {cap4} {hex} {cap4} {hex} {cap4} {hex}')
    new_lookup('reflow_numbers_fwd', 'gsub_contextchain')
    new_coverage('{dec} {cap5} {dec} {cap5} {dec} {cap5} {dec} {cap5} {dec}'
                 ' | {cap5} @<insert_separator> | {dec}')

    # Remove unused capture markers
    new_lookup('release_numbers', 'gsub_contextchain')
    new_coverage('| {hex} @<release_digit> {anycap} |')

    # convert separators into commas or apostrophes (TBD, dots?)
    new_glyph_rule('comma_separator', 'gsub_single', Features.COMMA)
    new_glyph_rule('apostrophe_separator', 'gsub_single', Features.APOSTROPHE)
    new_glyph_rule('dot_separator', 'gsub_single', Features.DOT)
    for d in [3,4,5]:
        glyph = font[f'thsp.sep{d}']
        glyph.addPosSub('comma_separator', f'thsp.comma{d}')
        glyph.addPosSub('apostrophe_separator', f'thsp.apostrophe{d}')
        glyph.addPosSub('dot_separator', f'thsp.dot{d}')

    if monospace:
        # I believe it's legal to fold all the lookups onto one line, but
        # fontforge doesn't seem to support it, so this is unrolled.  It might
        # be that the multi-lookup form of the table was always split into
        # separate entries anyway.  I do not know.

        # TODO: Another mode, like huddle, but where where digits are repelled
        # by the thousand separator.  This also minimises move distance but
        # will make groups have irregular spacing.  But the thousand separator
        # gap is always full-sized.
        if huddle:
            rules = [
                '{dotsep5} | {dec} @<rt_1_2> | {dec} {dec} {dec} {dec} {anysep5}',
                '{dotsep5} {dec_rt_1_2} | {dec} @<rt_1_4> | {dec} {dec} {dec} {anysep5}',
                # middle digit doesn't move
                '{dotsep5} {dec_rt_1_2} {dec_rt_1_4} {dec} | {dec} @<lf_1_4> | {dec} {anysep5}',
                '{dotsep5} {dec_rt_1_2} {dec_rt_1_4} {dec} {dec_lf_1_4} | {dec} @<lf_1_2> | {anysep5}',
                '{anysep4} | {hex} @<rt_1_2> | {hex} {hex} {hex}',
                '{anysep4} {hex_rt_1_2} | {hex} @<rt_1_6> | {hex} {hex}',
                '{anysep4} {hex_rt_1_2} {hex_rt_1_6} | {hex} @<lf_1_6> | {hex}',
                '{anysep4} {hex_rt_1_2} {hex_rt_1_6} {hex_lf_1_6} | {hex} @<lf_1_2> |',
                '{anysep3} | {dec} @<rt_1_2> | {dec} {dec}',
                # middle digit doesn't move
                '{anysep3} {dec_rt_1_2} {dec} | {dec} @<lf_1_2> |',
            ]
        else:
            rules = [
                # first digit doesn't move
                '{dotsep5} {dec} | {dec} @<lf_1_4> | {dec} {dec} {dec} {anysep5}',
                '{dotsep5} {dec} {dec_lf_1_4} | {dec} @<lf_1_2> | {dec} {dec} {anysep5}',
                '{dotsep5} {dec} {dec_lf_1_4} {dec_lf_1_2} | {dec} @<lf_3_4> | {dec} {anysep5}',
                '{dotsep5} {dec} {dec_lf_1_4} {dec_lf_1_2} {dec_lf_3_4} | {dec} @<lf_1_1> | {anysep5}',
                '{anysep4} | {hex} @<rt_1_1> | {hex} {hex} {hex}',
                '{anysep4} {hex_rt_1_1} | {hex} @<rt_2_3> | {hex} {hex}',
                '{anysep4} {hex_rt_1_1} {hex_rt_2_3} | {hex} @<rt_1_3> | {hex}',
                # last digit doesn't move
                '{anysep3} | {dec} @<rt_1_1> | {dec} {dec}',
                '{anysep3} {dec_rt_1_1} | {dec} @<rt_1_2> | {dec}',
                # last digit doesn't move
            ]

        useful_adjustments = {}
        pat = re.compile(r'{([a-z_0-9]+)} @<([a-z_0-9]+)>')
        for r in rules:
            match = pat.search(r)
            name, digits = match.group(2, 1)
            digits = set(classes[digits])
            digits |= useful_adjustments.get(name, set())
            useful_adjustments[name] = digits

        if terminal:
            for name, glyphs in useful_adjustments.items():
                new_glyph_rule(name, 'gsub_single')
                for g in glyphs:
                    adjusted_g = g+'.'+name
                    new_glyph(font, adjusted_g, g, adjustments[name])
                    font[g].addPosSub(name, adjusted_g)

            new_lookup('pinch_digits', 'gsub_contextchain')
        else:
            # switch to gpos
            curr_lookup = None

            for name, glyphs in useful_adjustments.items():
                new_glyph_rule(name, 'gpos_single')
                for g in glyphs:
                    font[g].addPosSub(name, adjustments[name], 0, 0, 0)

            new_lookup('pinch_digits', 'gpos_contextchain')

        for r in rules:
            new_ctx_subtable('coverage', r)

    return font


def main(inputs, output, always_on, rename, **kwargs):
    write_ttc = output.lower().endswith('.ttc')
    if always_on:
        Features.make_always(always_on)
    ttc_fonts = []
    n = 0
    for font_file in inputs:
        for font_name in fontforge.fontsInFile(font_file.name):
            font_id = f'{font_file.name}({font_name})'
            font = fontforge.open(font_id)
            if rename:
                rename_font(font, rename)
            font = patch_a_font(font, **kwargs)
            if write_ttc:
                ttc_fonts.append(font)
            else:
                filename = output
                with contextlib.suppress(TypeError):
                    filename = output % n
                    n = n + 1
                with contextlib.suppress(TypeError):
                    filename = output % font.fullname
                #font.generateFeatureFile(os.path.splitext(filename)[0] + '.fea')
                font.generate(filename)
                print('saved: ', filename)
                font.close()

    if ttc_fonts:
        ttc_fonts[0].generateTtc(output, ttc_fonts[1:],
                ttcflags=('merge',), layer=ttc_fonts[0].activeLayer)
        print('saved: ', output)
    for font in ttc_fonts:
        font.close()


def float_or_pct(string):
    if string[-1] == '%':
        return float(string[:-1]) * 0.01
    return float(string)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=('Add font-based digit grouping. ')
    )
    parser.add_argument('inputs', metavar='filename',
            help='Font files to patch.',
            nargs='+', type=argparse.FileType('rb'))
    parser.add_argument('-o', '--output', metavar='filename',
            help='Output filename or %%-format string (.ttf or .ttc).',
            nargs='?', default='%s.ttf')

    parser.add_argument('--monospace',
            help='Squeeze numbers together to fit original spacing.',
            default=False, action='store_true')
    parser.add_argument('--terminal',
            help='Use GSUB instead of GPOS rules, creating new glyphs.',
            default=False, action='store_true')
    parser.add_argument('--before',
            help='Insert new rules before existing GSUB rules, not after.',
            default=False, action='store_true')
    parser.add_argument('--always-on', metavar='feature',
            help='Turn feature on without further configuration.',
            nargs='?', default=None, const='dgsp')
    parser.add_argument('--huddle',
            help='Huddle digit groups towards centre to reduce clipping.',
            default=False, action='store_true')
    parser.add_argument('--gap-size',
            help='size of space for thousand separator.',
            type=str, default=",")
    #parser.add_argument('--shrink-x',
    #        help='Horizontal scale for digits being repositioned.',
    #        type=float_or_pct, default=1.0)
    #parser.add_argument('--shrink-y',
    #        help='Vertical scale for digits being repositioned.',
    #        type=float_or_pct, default=1.0)
    parser.add_argument('--rename', metavar='suffix',
            help='Modify font name.',
            nargs='?', default='DG', const='DG')
    parser.add_argument('--no-rename',
            dest='rename', action='store_const', const=None)

    main(**vars(parser.parse_args()))
