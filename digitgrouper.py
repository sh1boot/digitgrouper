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
TSEP_FEATURE = ( 'thsp', SCRIPTS )

class deferred_map:
    def __init__(self, function, sequence):
        self._f = function
        self._sequence = sequence

    def __iter__(self):
        return map(self._f, self._sequence)
    def __getitem__(self, i):
        return self._f(self._sequence[ord(i) if isinstance(i, str) else i])

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


def find_first_available(font, chars):
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

    glyph = find_first_available(font, gap_size if gap_size else '\N{THIN SPACE},. ')
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
    return glyph

def patch_a_font(font, monospace, gap_size, shrink_x, shrink_y):
    font.encoding = 'ISO10646'
    names = deferred_map(lambda o: o.glyphname, font)
    sizes = deferred_map(lambda o: o.width, font)

    gap_size = find_gap_size(font, gap_size)

    new_glyph(font, 'thsp.separator', find_first_available(font, '\N{THIN SPACE} ').glyphname)
    new_glyph(font, 'thsp.capture3', 'z')
    new_glyph(font, 'thsp.capture4', 'y')
    new_glyph(font, 'thsp.capture5', 'x')

    dec_group = collect_equivalents(font, '0123456789')
    hex_group = dec_group | collect_equivalents(font, 'abcdefABCDEF')
    dsep_group = collect_equivalents(font, '.')
    capture_group = [ 'thsp.capture3', 'thsp.capture4', 'thsp.capture5' ]

    print(f'decimals: {dec_group}')
    print(f'hexadecimals: {hex_group}')

    classes = {
        'dec': dec_group,
        'hex': hex_group,
        'sep': ['thsp.separator'],
        'cap3': ['thsp.capture3'],
        'cap4': ['thsp.capture4'],
        'cap5': ['thsp.capture5'],
        'anycap': capture_group,
        'zero': collect_equivalents(font, '0'),
        'xx': collect_equivalents(font, 'bBoOxX'),
        'dot': dsep_group,
        'dotsep': dsep_group | {'thsp.separator'},
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

    def new_subtable():
        nonlocal curr_lookup, subtable_index
        name = f'{curr_lookup}-{subtable_index}'
        if subtable_index:
            after = f'{curr_lookup}-{subtable_index-1}'
            font.addLookupSubtable(curr_lookup, name, after)
        else:
            font.addLookupSubtable(curr_lookup, name)
        subtable_index += 1
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

    # An empty rule to do nothing
    new_lookup('nop', 'gsub_single')

    # Rules to mark every digit in a string
    new_lookup('capture_3digit', 'gsub_multiple'); capture_3digit = new_subtable()
    new_lookup('capture_4digit', 'gsub_multiple'); capture_4digit = new_subtable()
    new_lookup('capture_5digit', 'gsub_multiple'); capture_5digit = new_subtable()
    # And a rule to remove those marks
    new_lookup('release_digit', 'gsub_ligature'); release_digit = new_subtable()
    for g in hex_group:
        font[g].addPosSub(capture_3digit, (g, 'thsp.capture3'))
        font[g].addPosSub(capture_4digit, (g, 'thsp.capture4'))
        font[g].addPosSub(capture_5digit, (g, 'thsp.capture5'))
        for cap in capture_group:
            font[g].addPosSub(release_digit, (g, cap))

    # And a rule to insert separator.
    new_lookup('insert_separator', 'gsub_single')
    insert_separator = new_subtable()
    for cap in capture_group:
        font[cap].addPosSub(insert_separator, 'thsp.separator')

    # Captures for all the different digit types
    new_lookup('capture_numbers', 'gsub_contextchain', (TSEP_FEATURE,))

    # ignore `..`, capture `.` as 5-digit, capture `0x` as 4-digit, capture
    # other numbers as 3-digit groups
    new_coverage('{dot} {dot} | {dec} @<nop> |')
    new_coverage(      '{dot} | {dec} @<capture_5digit> | {dec} {dec} {dec} {dec}')
    new_coverage('{zero} {xx} | {hex} @<capture_4digit> | {hex} {hex} {hex} {hex}')
    new_coverage(      '{dec} | {dec} @<capture_3digit> | {dec} {dec} {dec} {dec}')
    # fill everything following a capture
    new_coverage('{cap3} | {dec} @<capture_3digit> |')
    new_coverage('{cap4} | {hex} @<capture_4digit> |')
    new_coverage('{cap5} | {dec} @<capture_5digit> |')

    # Convert every nth capture into a digit group
    new_lookup('reflow_numbers_a', 'gsub_reversecchain', (TSEP_FEATURE,))
    new_rev_coverage('| {cap3} => {sep} | {dec} {cap3} {dec} {cap3} {dec}')
    new_rev_coverage('| {cap4} => {sep} | {hex} {cap4} {hex} {cap4} {hex} {cap4} {hex}')
    new_lookup('reflow_numbers_b', 'gsub_contextchain', (TSEP_FEATURE,))
    new_coverage('{dec} {cap5} {dec} {cap5} {dec} {cap5} {dec} {cap5} {dec} | {cap5} @<insert_separator> | {dec}')

    # Remove unused capture markers
    new_lookup('release_numbers', 'gsub_contextchain', (TSEP_FEATURE,))   # gsub_ligature?
    new_coverage('| {hex} @<release_digit> {anycap} |')

    if monospace:
        font['thsp.separator'].width = 0
        # switch to gpos
        curr_lookup = None
        new_lookup('lf_1_6', 'gpos_single'); lf_1_6 = new_subtable()
        new_lookup('rt_1_6', 'gpos_single'); rt_1_6 = new_subtable()
        new_lookup('lf_1_4', 'gpos_single'); lf_1_4 = new_subtable()
        new_lookup('centre', 'gpos_single');
        new_lookup('rt_1_4', 'gpos_single'); rt_1_4 = new_subtable()
        new_lookup('lf_1_2', 'gpos_single'); lf_1_2 = new_subtable()
        new_lookup('rt_1_2', 'gpos_single'); rt_1_2 = new_subtable()
        for g in hex_group:
            font[g].addPosSub(lf_1_6,-(gap_size // 6), 0, 0, 0)
            font[g].addPosSub(rt_1_6, (gap_size // 6), 0, 0, 0)
            font[g].addPosSub(lf_1_4,-(gap_size // 4), 0, 0, 0)
            font[g].addPosSub(rt_1_4, (gap_size // 4), 0, 0, 0)
            font[g].addPosSub(lf_1_2,-(gap_size // 2), 0, 0, 0)
            font[g].addPosSub(rt_1_2, (gap_size // 2), 0, 0, 0)

        new_lookup('pinch_digits', 'gpos_contextchain', (TSEP_FEATURE,))
        if False:
            # This seems to emit only a single subtable reference, which will
            # not do.
            rules = [
                '{dotsep} | {dec} @<rt_1_2> {dec} @<rt_1_4> {dec} @<centre> {dec} @<lf_1_4> {dec} @<lf_1_2> |',# {sep}',
                '{sep} | {hex} @<rt_1_2> {hex} @<rt_1_6> {hex} @<lf_1_6> {hex} @<lf_1_2> |',# {dotsep}',
                '{sep} | {dec} @<rt_1_2> {dec} @<centre> {dec} @<lf_1_2>',# | {dotsep}',
            ]
        else:
            rules = [
                '{dotsep} | {dec} @<rt_1_2> | {dec} {dec} {dec} {dec}',# {sep}',
                '{dotsep} {dec} | {dec} @<rt_1_4> | {dec} {dec} {dec}',# {sep}',
                '{dotsep} {dec} {dec} {dec} | {dec} @<lf_1_4> | {dec}',# {sep}',
                '{dotsep} {dec} {dec} {dec} {dec} | {dec} @<lf_1_2> |',# {sep}',
                '{sep} | {hex} @<rt_1_2> | {hex} {hex} {hex}',# {dotsep}',
                '{sep} {hex} | {hex} @<rt_1_6> | {hex} {hex}',# {dotsep}',
                '{sep} {hex} {hex} | {hex} @<lf_1_6> | {hex}',# {dotsep}',
                '{sep} {hex} {hex} {hex} | {hex} @<lf_1_2> |',# {dotsep}',
                '{sep} | {dec} @<rt_1_2> | {dec} {dec}',# {dotsep}',
                '{sep} {dec} {dec} | {dec} @<lf_1_2> |',# {dotsep}',
            ]
        for r in rules:
            new_ctx_subtable('coverage', r)

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
    return True


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
