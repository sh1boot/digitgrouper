#!/usr/bin/env python3
import argparse
import fontforge

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
ALL_MODES = (MAIN_FEATURE, COMMA_FEATURE, APSTR_FEATURE)
HEXADECIMAL_MODE = (('dghx', SCRIPTS),)
DECIMAL_COMMA_MODE = (('dgdc', SCRIPTS),)


def collect_equivalents(font, basis='0123456789'):
    result = set()
    for c in basis:
        glyph = font[ord(c)]
        name = glyph.glyphname
        result.add(name)
        additions = set()
        for sub in glyph.getPosSub('*'):
            if sub[1] in { 'Substitution', 'AltSubs', 'MultSubs' }:
                additions |= set(sub[2:])
        # TODO: should recurse, maybe...
        #result |= additions
        if additions:
            print(f'  would add {str(additions)} to {name}')
    return result


def find_first(font, chars):
    for c in chars:
        if ord(c) in font:
            return font[ord(c)]
    return None


def find_gap_size(font, gap_size):
    try:
        result = int(gap_size)
        if result > 0: return result
    except:
        pass

    glyph = find_first(font, gap_size if gap_size else '\N{THIN SPACE},. ')
    if glyph: gap_size = glyph.width

    # if suggested gap size is the size of a 0 it's probably
    # a monospaced font, so use the default monospace gap.
    size_of_0 = font[ord('0')].width
    if gap_size > size_of_0 // 2: gap_size = size_of_0 // 3
    return gap_size


def new_glyph(font, name, source=None):
    glyph = font.createChar(-1, name)
    if source:
        glyph.addReference(source)
        glyph.useRefsMetrics(source)
    return glyph


def patch_a_font(font, monospace, gap_size, shrink_x, shrink_y):
    font.encoding = 'ISO10646'

    gap_size = find_gap_size(font, gap_size)
    print(f'zero: {font[ord("0")].width}, gap_size: {gap_size}')

    new_glyph(font, 'thsp.sep3', find_first(font, '\N{THIN SPACE} ').glyphname)
    new_glyph(font, 'thsp.sep4', find_first(font, '\N{THIN SPACE} ').glyphname)
    new_glyph(font, 'thsp.sep5', find_first(font, '\N{THIN SPACE} ').glyphname)
    new_glyph(font, 'thsp.capture3', 'z')
    new_glyph(font, 'thsp.capture4', 'y')
    new_glyph(font, 'thsp.capture5', 'x')
    new_glyph(font, 'thsp.avoid', 'v')

    dec_group = collect_equivalents(font, '0123456789')
    hex_group = dec_group | collect_equivalents(font, 'abcdefABCDEF')
    dsep_group = collect_equivalents(font, '.,')
    capture_group = [ 'thsp.capture3', 'thsp.capture4', 'thsp.capture5', 'thsp.avoid' ]

    print(f'decimals: {dec_group}')
    print(f'hexadecimals: {hex_group}')

    classes = {
        'dec': dec_group,
        'hex': hex_group,
        'sep3': ['thsp.sep3'],
        'sep4': ['thsp.sep4'],
        'sep5': ['thsp.sep5'],
        'cap3': ['thsp.capture3'],
        'cap4': ['thsp.capture4'],
        'cap5': ['thsp.capture5'],
        'avoid': ['thsp.avoid'],
        'anycap': capture_group,
        'zero': collect_equivalents(font, '0'),
        'xx': collect_equivalents(font, 'bBoOxX'),
        'dot': collect_equivalents(font, '.'),
        'comma': collect_equivalents(font, ','),
        'dotsep3': dsep_group | {'thsp.sep3'},
        'dotsep4': dsep_group | {'thsp.sep4'},
        'dotsep5': dsep_group | {'thsp.sep5'},
    }
    classes_fmt = {
        k: '[ ' + ' '.join(v) + ' ]' for k,v in classes.items()
    }

    curr_lookup = None
    subtable_index = 0
    def new_lookup(name, lu_type, features=()):
        nonlocal curr_lookup, subtable_index
        if curr_lookup:
            font.addLookup(name, lu_type, None, features, curr_lookup)
        else:
            font.addLookup(name, lu_type, None, features)
        curr_lookup = name
        subtable_index = 0

    def new_glyph_rule(name, lu_type, features=()):
        new_lookup(name, lu_type, features)
        font.addLookupSubtable(name, name)
        return name


    def new_ctx_subtable(st_type, rule):
        nonlocal curr_lookup, subtable_index, classes_fmt
        name = f'{curr_lookup}-{subtable_index}'
        if subtable_index:
            after = f'{curr_lookup}-{subtable_index-1}'
            font.addContextualSubtable(curr_lookup, name, st_type,
                    rule.format(**classes_fmt), afterSubtable=after)
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
    # What I have called 'glyph rules' here are substitutions which are
    # described within the glyph rather than within context rules.  The lookup
    # and subtable are given the same name so they can be used interchangeably
    # (glyphs reference the subtable, and subtable rules reference the lookup).

    # Rules to mark any digit in a string
    new_glyph_rule('capture_3digit', 'gsub_multiple')
    new_glyph_rule('capture_4digit', 'gsub_multiple')
    new_glyph_rule('capture_5digit', 'gsub_multiple')
    new_glyph_rule('capture_avoid', 'gsub_multiple')
    # And a rule to remove those marks
    new_glyph_rule('release_digit', 'gsub_ligature')
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
    new_lookup('capture_as_hex', 'gsub_contextchain', HEXADECIMAL_MODE)
    new_coverage('| {hex} @<capture_4digit> | {hex} {hex} {hex} {hex}')

    new_lookup('comma_as_decimal', 'gsub_contextchain', DECIMAL_COMMA_MODE)
    # if it's `n,nnnn` that's a decimal number
    new_coverage('{dec} {comma} | {dec} @<capture_5digit> | {dec} {dec} {dec} {dec}')
    # otherwise if it's `,nnnnn` it's not clear what it is, so avoid it.
    new_coverage(      '{comma} | {dec} @<capture_avoid> | {dec} {dec}')
    # and we switch off support for decimal dot, while we're here.
    new_coverage('        {dot} | {dec} @<capture_avoid> | {dec} {dec} {dec}')

    # Captures for all the different digit types
    new_lookup('capture_numbers', 'gsub_contextchain', ALL_MODES)

    # if it's `..nnnnn`, that's probably an integer following a rage.
    new_coverage('{dot} {dot} | {dec} @<capture_3digit> | {dec} {dec} {dec} {dec}')
    # if it's `n.nnnn` that's a decimal number
    new_coverage('{dec} {dot} | {dec} @<capture_5digit> | {dec} {dec} {dec} {dec}')
    # otherwise if it's `.nnnnn` it's not clear what it is, so avoid it.
    new_coverage(      '{dot} | {dec} @<capture_avoid> | {dec} {dec}')

    ## TODO: consider: excluding `x` in middle of number (is it `XXXxYYY`?)
    new_coverage('{zero} {xx} | {hex} @<capture_4digit> | {hex} {hex} {hex} {hex}')
    new_coverage(      '{dec} | {dec} @<capture_3digit> | {dec} {dec} {dec} {dec}')
    # fill everything following a capture to match
    new_coverage('{cap3} | {dec} @<capture_3digit> |')
    new_coverage('{cap4} | {hex} @<capture_4digit> |')
    new_coverage('{cap5} | {dec} @<capture_5digit> |')
    new_coverage('{avoid} | {dec} @<capture_avoid> |')

    # Convert every nth capture into a digit group
    new_lookup('reflow_numbers_rev', 'gsub_reversecchain', ALL_MODES)
    new_rev_coverage('| {cap3} => {sep3} | {dec} {cap3} {dec} {cap3} {dec}')
    new_rev_coverage('| {cap4} => {sep4} | {hex} {cap4} {hex} {cap4} {hex} {cap4} {hex}')
    new_lookup('reflow_numbers_fwd', 'gsub_contextchain', ALL_MODES)
    new_coverage('{dec} {cap5} {dec} {cap5} {dec} {cap5} {dec} {cap5} {dec} | {cap5} @<insert_separator> | {dec}')

    # Remove unused capture markers
    new_lookup('release_numbers', 'gsub_contextchain', ALL_MODES)
    new_coverage('| {hex} @<release_digit> {anycap} |')

    # convert separators into commas or apostrophes (TBD, dots?)
    new_glyph_rule('comma_separator', 'gsub_single', (COMMA_FEATURE,))
    new_glyph_rule('apostrophe_separator', 'gsub_single', (APSTR_FEATURE,))
    for g in [ font[f'thsp.sep{d}'] for d in [3,4,5] ]:
        g.addPosSub('comma_separator', font[ord(',')].glyphname)
        g.addPosSub('apostrophe_separator', font[ord("'")].glyphname)
        # TODO: monospaced fixups, somehow.

    if monospace:
        for g in [ font[f'thsp.sep{d}'] for d in [3,4,5] ]:
            g.glyphclass = 'mark'
            g.left_side_bearing = int(g.left_side_bearing) - g.width // 2
            g.width = 0

        # switch to gpos
        curr_lookup = None

        new_glyph_rule('lf_1_6', 'gpos_single')
        new_glyph_rule('rt_1_6', 'gpos_single')
        new_glyph_rule('lf_1_4', 'gpos_single')
        new_glyph_rule('rt_1_4', 'gpos_single')
        new_glyph_rule('lf_1_2', 'gpos_single')
        new_glyph_rule('rt_1_2', 'gpos_single')
        new_glyph_rule('lf_3_4', 'gpos_single')
        new_glyph_rule('rt_2_3', 'gpos_single')
        new_glyph_rule('rt_1_3', 'gpos_single')
        new_glyph_rule('lf_1_1', 'gpos_single')
        new_glyph_rule('rt_1_1', 'gpos_single')
        for g in hex_group:
            font[g].addPosSub('lf_1_6',-1 * (gap_size // 6), 0, 0, 0)
            font[g].addPosSub('rt_1_6', 1 * (gap_size // 6), 0, 0, 0)
            font[g].addPosSub('lf_1_4',-1 * (gap_size // 4), 0, 0, 0)
            font[g].addPosSub('rt_1_4', 1 * (gap_size // 4), 0, 0, 0)
            font[g].addPosSub('lf_1_2',-1 * (gap_size // 2), 0, 0, 0)
            font[g].addPosSub('rt_1_2', 1 * (gap_size // 2), 0, 0, 0)
            font[g].addPosSub('lf_3_4',-3 * (gap_size // 4), 0, 0, 0)
            font[g].addPosSub('rt_1_3', 1 * (gap_size // 3), 0, 0, 0)
            font[g].addPosSub('rt_2_3', 2 * (gap_size // 3), 0, 0, 0)
            font[g].addPosSub('lf_1_1',-1 * (gap_size // 1), 0, 0, 0)
            font[g].addPosSub('rt_1_1', 1 * (gap_size // 1), 0, 0, 0)

        new_lookup('pinch_digits', 'gpos_contextchain', ALL_MODES)
        # I believe it's legal to fold all the lookups onto one line, but
        # fontforge doesn't seem to support it, so this is unrolled.
        # TODO: user-selectable thing here:
        if False:
            rules = [
                '{dotsep5} | {dec} @<rt_1_2> | {dec} {dec} {dec} {dec} {sep5}',
                '{dotsep5} {dec} | {dec} @<rt_1_4> | {dec} {dec} {dec} {sep5}',
                # middle digit doesn't move
                '{dotsep5} {dec} {dec} {dec} | {dec} @<lf_1_4> | {dec} {sep5}',
                '{dotsep5} {dec} {dec} {dec} {dec} | {dec} @<lf_1_2> | {sep5}',
                '{sep4} | {hex} @<rt_1_2> | {hex} {hex} {hex}',
                '{sep4} {hex} | {hex} @<rt_1_6> | {hex} {hex}',
                '{sep4} {hex} {hex} | {hex} @<lf_1_6> | {hex}',
                '{sep4} {hex} {hex} {hex} | {hex} @<lf_1_2> |',
                '{sep3} | {dec} @<rt_1_2> | {dec} {dec}',
                # middle digit doesn't move
                '{sep3} {dec} {dec} | {dec} @<lf_1_2> |',
            ]
        else:
            rules = [
                # first digit doesn't move
                '{dotsep5} {dec} | {dec} @<lf_1_4> | {dec} {dec} {dec} {sep5}',
                '{dotsep5} {dec} {dec} | {dec} @<lf_1_2> | {dec} {dec} {sep5}',
                '{dotsep5} {dec} {dec} {dec} | {dec} @<lf_3_4> | {dec} {sep5}',
                '{dotsep5} {dec} {dec} {dec} {dec} | {dec} @<lf_1_1> | {sep5}',
                '{sep4} | {hex} @<rt_1_1> | {hex} {hex} {hex}',
                '{sep4} {hex} | {hex} @<rt_2_3> | {hex} {hex}',
                '{sep4} {hex} {hex} | {hex} @<rt_1_3> | {hex}',
                # last digit doesn't move
                '{sep3} | {dec} @<rt_1_1> | {dec} {dec}',
                '{sep3} {dec} | {dec} @<rt_1_2> | {dec}',
                # last digit doesn't move
            ]
        # TODO: also there's the "away from separator" spacing to try
        for r in rules:
            new_ctx_subtable('coverage', r)
    else:  # if not monospace
        # TODO: this isn't really working :(
        for g in [ font[f'thsp.sep{d}'] for d in [3,4,5] ]:
            g.left_side_bearing = int(g.left_side_bearing) - (g.width - gap_size) // 2
            g.width = gap_size
            # might need to unattach reference metrics or something?

    font.generateFeatureFile('output.fea')
    return font


def main(font_list, **kwargs):
    results = []
    for font_file in font_list:
        for font_name in fontforge.fontsInFile(font_file.name):
            font_id = f'{font_file.name}({font_name})'
            font = fontforge.open(font_id)
            results.append(patch_a_font(font, **kwargs))
    if len(results) > 1:
        results[0].generateTtc('output.ttc', results[1:])
    else:
        results[0].generate('output.ttf')
    for font in results: font.close()


def float_or_pct(string):
    if string[-1] == '%':
        return float(string[:-1]) * 0.01;
    return float(string)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=('Add font-based digit grouping. ')
    )
    parser.add_argument('font_list', metavar='font', nargs='*',
            type=argparse.FileType('rb'), help='font files to patch')

    parser.add_argument('--monospace', default=False,
            action='store_true',
            help='Squeeze numbers together to occupy original space')
    parser.add_argument('--gap-size', type=str, default=",",
            help='size of space for thousand separator, try 300 or ","')
    parser.add_argument('--shrink_x', type=float_or_pct, default=1.0,
            help='horizontal scale to apply to digits being'
                ' repositioned')
    parser.add_argument('--shrink_y', type=float_or_pct, default=1.0,
            help='vertical scale to apply to the digits being'
                ' repositioned')
    main(**vars(parser.parse_args()))
