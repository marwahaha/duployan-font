# Copyright 2018 David Corbett
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import division

__all__ = ['augment']

import collections
import math
import os
import tempfile

import fontforge
import psMat

BASELINE = 402
DEFAULT_SIDE_BEARING = 85
RADIUS = 100
STROKE_WIDTH = 70
CURSIVE_LOOKUP = "'curs'"
CURSIVE_SUBTABLE = CURSIVE_LOOKUP + '-1'
CURSIVE_ANCHOR = 'cursive'
RELATIVE_1_LOOKUP = "'mark' relative mark inside or above"
RELATIVE_1_SUBTABLE = RELATIVE_1_LOOKUP + '-1'
RELATIVE_1_ANCHOR = 'rel1'
RELATIVE_2_LOOKUP = "'mark' relative mark outside or below"
RELATIVE_2_SUBTABLE = RELATIVE_2_LOOKUP + '-1'
RELATIVE_2_ANCHOR = 'rel2'
ABOVE_LOOKUP = "'mark' above"
ABOVE_SUBTABLE = ABOVE_LOOKUP + '-1'
ABOVE_ANCHOR = 'abv'
BELOW_LOOKUP = "'mark' below"
BELOW_SUBTABLE = BELOW_LOOKUP + '-1'
BELOW_ANCHOR = 'blw'

def add_lookup(font, lookup, lookup_type, flags, feature, subtable, anchor_class):
    font.addLookup(lookup,
        lookup_type,
        flags,
        ((feature, (('dupl', ('dflt',)),)),))
    font.addLookupSubtable(lookup, subtable)
    font.addAnchorClass(subtable, anchor_class)

def add_lookups(font):
    add_lookup(font,
        CURSIVE_LOOKUP,
        'gpos_cursive',
        ('ignore_marks',),
        'curs',
        CURSIVE_SUBTABLE,
        CURSIVE_ANCHOR)
    add_lookup(font,
        RELATIVE_1_LOOKUP,
        'gpos_mark2base',
        (),
        'mark',
        RELATIVE_1_SUBTABLE,
        RELATIVE_1_ANCHOR)
    add_lookup(font,
        RELATIVE_2_LOOKUP,
        'gpos_mark2base',
        (),
        'mark',
        RELATIVE_2_SUBTABLE,
        RELATIVE_2_ANCHOR)
    add_lookup(font,
        ABOVE_LOOKUP,
        'gpos_mark2base',
        (),
        'mark',
        ABOVE_SUBTABLE,
        ABOVE_ANCHOR)
    add_lookup(font,
        BELOW_LOOKUP,
        'gpos_mark2base',
        (),
        'mark',
        BELOW_SUBTABLE,
        BELOW_ANCHOR)

class Enum(object):
    def __init__(self, names):
        for i, name in enumerate(names):
            setattr(self, name, i)

TYPE = Enum([
    'JOINING',
    'ORIENTING',
    'NON_JOINING',
])

class Context(object):
    def __init__(self, angle=None, clockwise=None):
        self.angle = angle
        self.clockwise = clockwise

    def __repr__(self):
        return 'Context({}, {})'.format(self.angle, self.clockwise)

    def __str__(self):
        if self.angle is None:
            return ''
        return '{}{}'.format(
            self.angle,
            '' if self.clockwise is None else 'neg' if self.clockwise else 'pos')

    def __eq__(self, other):
        return self.angle == other.angle and self.clockwise == other.clockwise

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(self.angle) ^ hash(self.clockwise)

def rect(r, theta):
    return (r * math.cos(theta), r * math.sin(theta))

class Space(object):
    def __init__(self, angle):
        self.angle = angle

    def __str__(self):
        return 'espace.{}'.format(self.angle)

    def __call__(self, glyph, pen, size, anchor, joining_type):
        if joining_type != TYPE.NON_JOINING:
            glyph.addAnchorPoint(CURSIVE_ANCHOR, 'entry', -size, 0)
            glyph.addAnchorPoint(CURSIVE_ANCHOR, 'exit', 0, 0)
            glyph.transform(psMat.rotate(math.radians(self.angle)), ('round',))

    def context_in(self):
        return Context()

    def context_out(self):
        return Context()

class Dot(object):
    def __str__(self):
        return 'point'

    def __call__(self, glyph, pen, size, anchor, joining_type):
        pen.moveTo((0, 0))
        pen.lineTo((0, 0))
        glyph.stroke('circular', STROKE_WIDTH, 'round')
        if anchor:
            glyph.addAnchorPoint(anchor, 'mark', *rect(0, 0))

    def context_in(self):
        return Context()

    def context_out(self):
        return Context()

class Line(object):
    def __init__(self, angle):
        self.angle = angle

    def __str__(self):
        name = ''
        if self.angle == 0:
            name = 'T'
        if self.angle == 30:
            name = 'L'
        if self.angle == 240:
            name = 'K'
        if self.angle == 270:
            name = 'P'
        if self.angle == 315:
            name = 'F'
        return 'ligne{}.{}'.format(name, self.angle)

    def __call__(self, glyph, pen, size, anchor, joining_type):
        pen.moveTo((0, 0))
        length = 500 * (size or 0.2) / (abs(math.sin(math.radians(self.angle))) or 1)
        pen.lineTo((length, 0))
        if anchor:
            glyph.addAnchorPoint(anchor, 'mark', *rect(length / 2, 0))
        else:
            if joining_type != TYPE.NON_JOINING:
                glyph.addAnchorPoint(CURSIVE_ANCHOR, 'entry', 0, 0)
                glyph.addAnchorPoint(CURSIVE_ANCHOR, 'exit', length, 0)
            if size == 2 and self.angle == 30:
                # Special case for U+1BC18 DUPLOYAN LETTER RH
                glyph.addAnchorPoint(RELATIVE_1_ANCHOR, 'base', length / 2 - 2 * STROKE_WIDTH, -STROKE_WIDTH)
                glyph.addAnchorPoint(RELATIVE_2_ANCHOR, 'base', length / 2 + 2 * STROKE_WIDTH, -STROKE_WIDTH)
            else:
                glyph.addAnchorPoint(RELATIVE_1_ANCHOR, 'base', length / 2, STROKE_WIDTH)
                glyph.addAnchorPoint(RELATIVE_2_ANCHOR, 'base', length / 2, -STROKE_WIDTH)
        glyph.transform(psMat.rotate(math.radians(self.angle)), ('round',))
        glyph.stroke('circular', STROKE_WIDTH, 'round')

    def context_in(self):
        return Context(self.angle)

    def context_out(self):
        return Context(self.angle)

class Curve(object):
    def __init__(self, angle_in, angle_out, clockwise):
        self.angle_in = angle_in
        self.angle_out = angle_out
        self.clockwise = clockwise

    def __str__(self):
        name = ''
        if self.angle_in == 0 and self.angle_out == 180 and self.clockwise:
            name = 'N'
        if self.angle_in == 90 and self.angle_out == 270 and self.clockwise:
            name = 'J'
        if self.angle_in == 180 and self.angle_out == 0 and not self.clockwise:
            name = 'M'
        if self.angle_in == 270 and self.angle_out == 90 and not self.clockwise:
            name = 'S'
        return 'courbe{}.{}.{}.{}'.format(
            name, self.angle_in, self.angle_out, 'neg' if self.clockwise else 'pos')

    def __call__(self, glyph, pen, size, anchor, joining_type):
        assert anchor is None
        angle_out = self.angle_out
        if self.clockwise and angle_out > self.angle_in:
            angle_out -= 360
        elif not self.clockwise and angle_out < self.angle_in:
            angle_out += 360
        a1 = (90 if self.clockwise else -90) + self.angle_in
        a2 = (90 if self.clockwise else -90) + angle_out
        r = RADIUS * size
        da = a2 - a1
        beziers_needed = int(math.ceil(abs(da) / 90))
        bezier_arc = da / beziers_needed
        cp = r * (4 / 3) * math.tan(math.pi / (2 * beziers_needed * 360 / da))
        cp_distance = math.hypot(cp, r)
        cp_angle = math.asin(cp / cp_distance)
        pen.moveTo(rect(r, math.radians(a1)))
        for i in range(1, beziers_needed + 1):
            theta0 = math.radians(a1 + (i - 1) * bezier_arc)
            p0 = rect(r, theta0)
            p1 = rect(cp_distance, theta0 + cp_angle)
            theta3 = math.radians(a2 if i == beziers_needed else a1 + i * bezier_arc)
            p3 = rect(r, theta3)
            p2 = rect(cp_distance, theta3 - cp_angle)
            pen.curveTo(p1, p2, p3)
        pen.endPath()
        glyph.stroke('circular', STROKE_WIDTH, 'round')
        relative_mark_angle = (a1 + a2) / 2
        if joining_type != TYPE.NON_JOINING:
            x = r * math.cos(math.radians(a1))
            y = r * math.sin(math.radians(a1))
            glyph.addAnchorPoint(CURSIVE_ANCHOR, 'entry', x, y)
            glyph.addAnchorPoint(CURSIVE_ANCHOR, 'exit', p3[0], p3[1])
        glyph.addAnchorPoint(RELATIVE_1_ANCHOR, 'base',
            *(rect(0, 0) if da > 180 else rect(
                min(STROKE_WIDTH, r - 2 * STROKE_WIDTH),
                math.radians(relative_mark_angle))))
        glyph.addAnchorPoint(RELATIVE_2_ANCHOR, 'base', *rect(r + 2 * STROKE_WIDTH, math.radians(relative_mark_angle)))
        if joining_type == TYPE.ORIENTING:
            glyph.addAnchorPoint(ABOVE_ANCHOR, 'base', *rect(r + 2 * STROKE_WIDTH, math.radians(90)))
            glyph.addAnchorPoint(BELOW_ANCHOR, 'base', *rect(r + 2 * STROKE_WIDTH, math.radians(270)))

    def contextualize(self, context_in, context_out):
        angle_in = context_in.angle
        angle_out = context_out.angle
        da = self.angle_out - self.angle_in
        if angle_in is None:
            if angle_out is not None:
                angle_in = (angle_out - da) % 360
            else:
                angle_in = self.angle_in
        return Curve(
            angle_in,
            (angle_in + da) % 360,
            (self.clockwise
                if angle_out is None or da != 180
                else (abs(angle_out - angle_in) >= 180) == (angle_out > angle_in)))

    def context_in(self):
        return Context(self.angle_in, self.clockwise)

    def context_out(self):
        return Context(self.angle_out, self.clockwise)

class Circle(object):
    def __init__(self, angle_in, angle_out, clockwise):
        self.angle_in = angle_in
        self.angle_out = angle_out
        self.clockwise = clockwise

    def __str__(self):
        return 'cercle.{}.{}.{}'.format(
            self.angle_in, self.angle_out, 'neg' if self.clockwise else 'pos')

    def __call__(self, glyph, pen, size, anchor, joining_type):
        assert anchor is None
        angle_out = self.angle_out
        if self.clockwise and self.angle_out > self.angle_in:
            angle_out -= 360
        elif not self.clockwise and self.angle_out < self.angle_in:
            angle_out += 360
        a1 = (90 if self.clockwise else -90) + self.angle_in
        a2 = (90 if self.clockwise else -90) + angle_out
        r = RADIUS * size
        cp = r * (4 / 3) * math.tan(math.pi / 8)
        pen.moveTo((0, r))
        pen.curveTo((cp, r), (r, cp), (r, 0))
        pen.curveTo((r, -cp), (cp, -r), (0, -r))
        pen.curveTo((-cp, -r), (-r, -cp), (-r, 0))
        pen.curveTo((-r, cp), (-cp, r), (0, r))
        pen.endPath()
        glyph.stroke('circular', STROKE_WIDTH, 'round')
        if joining_type != TYPE.NON_JOINING:
            glyph.addAnchorPoint(CURSIVE_ANCHOR, 'entry', *rect(r, math.radians(a1)))
            glyph.addAnchorPoint(CURSIVE_ANCHOR, 'exit', *rect(r, math.radians(a2)))
        glyph.addAnchorPoint(RELATIVE_1_ANCHOR, 'base', *rect(0, 0))
        glyph.addAnchorPoint(RELATIVE_2_ANCHOR, 'base', *rect(r + 2 * STROKE_WIDTH, math.radians(90)))

    def contextualize(self, context_in, context_out):
        angle_in = context_in.angle
        angle_out = context_out.angle
        if angle_in is None:
            if angle_out is None:
                angle_in = 0
            else:
                angle_in = angle_out
        if angle_out is None:
            angle_out = angle_in
        clockwise_from_adjacent_curve = (
            context_in.clockwise
                if context_in.clockwise is not None
                else context_out.clockwise)
        if angle_in == angle_out:
            return Circle(
                angle_in,
                angle_out,
                clockwise_from_adjacent_curve
                    if clockwise_from_adjacent_curve is not None
                    else self.clockwise)
        da = abs(angle_out - angle_in)
        clockwise_ignoring_curvature = (da >= 180) != (angle_out > angle_in)
        clockwise = (
            clockwise_from_adjacent_curve
                if clockwise_from_adjacent_curve is not None
                else clockwise_ignoring_curvature)
        shape = Curve if clockwise == clockwise_ignoring_curvature else Circle
        return shape(angle_in, angle_out, clockwise)

    def context_in(self):
        return Context(self.angle_in, self.clockwise)

    def context_out(self):
        return Context(self.angle_out, self.clockwise)

class Schema(object):
    def __init__(
            self,
            cp,
            path,
            size,
            joining_type=TYPE.JOINING,
            side_bearing=DEFAULT_SIDE_BEARING,
            anchor=None,
            marks=None,
            default_ignorable=False,
            origin='nom'):
        assert not (marks and anchor), 'A schema has both marks {} and anchor {}'.format(marks, anchor)
        self.cp = cp
        self.path = path
        self.size = size
        self.joining_type = joining_type
        self.side_bearing = side_bearing
        self.anchor = anchor
        self.marks = marks or []
        self.default_ignorable = default_ignorable
        self.origin = origin
        self._hash = self._calculate_hash()

    def _calculate_hash(self):
        return (hash(self.cp) ^
            hash(str(self.path)) ^
            hash(self.size) ^
            hash(self.joining_type) ^
            hash(self.anchor) ^
            hash(self.default_ignorable) ^
            hash(self.origin))

    def __eq__(self, other):
        return (
            self._hash == other._hash and
            self.cp == other.cp and
            self.size == other.size and
            self.joining_type == other.joining_type and
            self.default_ignorable == other.default_ignorable and
            self.anchor == other.anchor and
            self.origin == other.origin and
            self.marks == other.marks and
            str(self.path) == str(other.path))

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return self._hash

    def __str__(self):
        return '{}.{}.{}{}{}{}'.format(
            self.path,
            self.size,
            str(self.side_bearing) + '.' if self.side_bearing != DEFAULT_SIDE_BEARING else '',
            '_' if self.joining_type != TYPE.ORIENTING else self.origin,
            '.' + self.anchor if self.anchor else '',
            '.' + '.'.join(map(str, self.marks)) if self.marks else '')

    def contextualize(self, context_in, context_out):
        assert self.joining_type == TYPE.ORIENTING
        return Schema(-1,
            self.path.contextualize(context_in, context_out),
            self.size,
            self.joining_type,
            self.side_bearing,
            origin='contextual_{}_{}'.format(context_in, context_out))

    def without_marks(self):
        return Schema(
            -1,
            self.path,
            self.size,
            self.joining_type,
            self.side_bearing,
            self.anchor,
            origin=self.origin)

def merge_feature(font, feature_string):
    fea_path = tempfile.mkstemp(suffix='.fea')[1]
    try:
        with open(fea_path, 'w') as fea:
            fea.write(feature_string)
        font.mergeFeature(fea_path)
    finally:
        os.remove(fea_path)

def wrap(tag, lookup):
    return ('feature {} {{\n'
        '    languagesystem dupl dflt;\n'
        '    lookupflag IgnoreMarks;\n'
        '{}}} {};\n').format(tag, lookup, tag)

class OrderedSet(collections.OrderedDict):
    def __init__(self, iterable=None):
        super(OrderedSet, self).__init__()
        if iterable:
            for item in iterable:
                self.add(item)

    def add(self, item):
        self[item] = None

class Substitution(object):
    def __init__(self, a1, a2, a3=None, a4=None):
        if a4 is None:
            assert a3 is None, 'Substitution takes 2 or 4 inputs, given 3'
            self.contexts_in = []
            self.inputs = a1
            self.contexts_out = []
            self.outputs = a2
        else:
            self.contexts_in = a1
            self.inputs = a2
            self.contexts_out = a3
            self.outputs = a4

    def __str__(self):
        def _s(glyphs, apostrophe=False):
            suffix = "'" if apostrophe else ''
            return ('@' + glyphs
                if isinstance(glyphs, str)
                else '{} '.format(suffix).join(map(str, glyphs))) + suffix
        return '    substitute {} {} {} by {};\n'.format(
            _s(self.contexts_in),
            _s(self.inputs, apostrophe=True),
            _s(self.contexts_out),
            _s(self.outputs))

class Lookup(object):
    def __init__(self, feature, script, language):
        self.feature = feature
        self.script = script
        self.language = language
        self.rules = []

    def __str__(self):
        return (
            'feature {} {{\n'
            '    languagesystem {} {};\n'
            '    lookupflag IgnoreMarks;\n'
            '{}'
            '}} {};\n'
            ).format(
                self.feature,
                self.script,
                self.language,
                ''.join(map(str, self.rules)), self.feature)

    def append(self, rule):
        self.rules.append(rule)

    def extend(self, other):
        assert self.feature == other.feature, "Incompatible features: '{}', '{}'".format(self.feature, other.feature)
        assert self.script == other.script, "Incompatible scripts: '{}', '{}'".format(self.script, other.script)
        assert self.language == other.language, "Incompatible languages: '{}', '{}'".format(self.language, other.language)
        self.rules.extend(other.rules)

def dont_ignore_default_ignorables(schemas, new_schemas):
    lookup_1 = Lookup('ccmp', 'dupl', 'dflt')
    lookup_2 = Lookup('ccmp', 'dupl', 'dflt')
    for schema in schemas:
        if schema.default_ignorable:
            lookup_1.append(Substitution([schema], [schema, schema]))
            lookup_2.append(Substitution([schema, schema], [schema]))
    return schemas, [lookup_1, lookup_2], {}

def decompose(schemas, new_schemas):
    lookup = Lookup('ccmp', 'dupl', 'dflt')
    output_schemas = OrderedSet()
    for schema in schemas:
        if schema.marks:
            substitution_output = [schema.without_marks()] + schema.marks
            lookup.append(Substitution([schema], substitution_output))
            for output_schema in substitution_output:
                output_schemas.add(output_schema)
        else:
            output_schemas.add(schema)
    return output_schemas, [lookup], {}

def join_with_previous(schemas, new_schemas):
    # TODO
    return schemas, [], {}

def join_with_next(schemas, new_schemas):
    # TODO
    return schemas, [], {}

def run_phases(all_input_schemas, phases):
    all_schemas = OrderedSet(all_input_schemas)
    all_lookups = []
    all_classes = {}
    for phase in phases:
        all_output_schemas = OrderedSet()
        new_input_schemas = OrderedSet(all_input_schemas)
        lookups = None
        in_phase = True
        while in_phase:
            in_phase = False
            output_schemas, output_lookups, classes = phase(all_input_schemas, new_input_schemas)
            new_input_schemas = OrderedSet()
            for output_schema in output_schemas:
                all_output_schemas.add(output_schema)
                if output_schema not in all_input_schemas:
                    all_input_schemas.add(output_schema)
                    new_input_schemas.add(output_schema)
                    in_phase = True
            if lookups is None:
                lookups = output_lookups
            else:
                assert len(lookups) == len(output_lookups), 'Incompatible lookup counts for phase {}'.format(phase)
                for i, lookup in enumerate(lookups):
                    lookup.extend(output_lookups[i])
        all_input_schemas = all_output_schemas
        all_schemas.update(all_input_schemas)
        all_lookups.extend(lookups)
        all_classes.update(classes)
    return all_schemas, all_lookups, all_classes

PHASES = [
    dont_ignore_default_ignorables,
    decompose,
    join_with_previous,
    join_with_next,
]

def classes_str(classes):
    return '\n'.join('@{} = [{}];'.format(cls, ' '.join(map(str, schemas))) for cls, schemas in classes.items())

class GlyphManager(object):
    def __init__(self, font, schemas, phases):
        self.font = font
        self.schemas = schemas
        self.phases = phases
        code_points = collections.defaultdict(int)
        for schema in schemas:
            if schema.cp != -1:
                code_points[schema.cp] += 1
        code_points = {cp: count for cp, count in code_points.items() if count > 1}
        assert not code_points, ('Duplicate code points:\n    ' +
            '\n    '.join(map(hex, sorted(code_points.keys()))))

    def add_altuni(self, cp, glyph_name):
        glyph = self.font.temporary[glyph_name]
        if cp != -1:
            new_altuni = ((cp, -1, 0),)
            if glyph.altuni is None:
                glyph.altuni = new_altuni
            else:
                glyph.altuni += new_altuni
        return glyph

    def draw_glyph_with_marks(self, schema, glyph_name):
        base_glyph = self.draw_glyph(schema.without_marks()).glyphname
        mark_glyphs = []
        for mark in schema.marks:
            mark_glyphs.append(self.draw_glyph(mark).glyphname)
        self.refresh()
        glyph = self.font.createChar(schema.cp, glyph_name)
        self.font.temporary[glyph_name] = glyph
        glyph.glyphclass = 'baseglyph'
        glyph.addReference(base_glyph)
        base_anchors = {p[0]: p for p in self.font[base_glyph].anchorPoints if p[1] == 'base'}
        for mark_glyph in mark_glyphs:
            mark_anchors = [p for p in self.font[mark_glyph].anchorPoints if p[1] == 'mark']
            assert len(mark_anchors) == 1
            mark_anchor = mark_anchors[0]
            base_anchor = base_anchors[mark_anchor[0]]
            glyph.addReference(mark_glyph, psMat.translate(
                base_anchor[2] - mark_anchor[2],
                base_anchor[3] - mark_anchor[3]))
        return glyph

    def draw_base_glyph(self, schema, glyph_name):
        glyph = self.font.createChar(schema.cp, glyph_name)
        self.font.temporary[glyph_name] = glyph
        glyph.glyphclass = 'mark' if schema.anchor else 'baseglyph'
        pen = glyph.glyphPen()
        schema.path(glyph, pen, schema.size, schema.anchor, schema.joining_type)
        return glyph

    def draw_glyph(self, schema):
        glyph_name = str(schema)
        if glyph_name in self.font.temporary:
            return self.add_altuni(schema.cp, glyph_name)
        if schema.marks:
            glyph = self.draw_glyph_with_marks(schema, glyph_name)
        else:
            glyph = self.draw_base_glyph(schema, glyph_name)
        glyph.left_side_bearing = schema.side_bearing
        glyph.right_side_bearing = schema.side_bearing
        bbox = glyph.boundingBox()
        center = (bbox[3] - bbox[1]) / 2 + bbox[1]
        glyph.transform(psMat.translate(0, BASELINE - center))
        return glyph

    def refresh(self):
        # Work around https://github.com/fontforge/fontforge/issues/3278
        sfd_path = 'refresh.sfd'
        assert not os.path.exists(sfd_path), '{} already exists'.format(sfd_path)
        self.font.save(sfd_path)
        temporary = self.font.temporary
        self.font = fontforge.open(sfd_path)
        self.font.temporary = temporary
        os.remove(sfd_path)

    def run(self):
        self.font.temporary = {}
        schemas, lookups, classes = run_phases(self.schemas, self.phases)
        for schema in schemas:
            glyph = self.draw_glyph(schema)
            if glyph.altuni:
                # This glyph has already been processed.
                continue
        self.refresh()
        merge_feature(self.font, '{}\n{}'.format(classes_str(classes), '\n'.join(map(str, lookups))))
        return self.font

SPACE = Space(0)
H = Dot()
P = Line(270)
T = Line(0)
F = Line(315)
K = Line(240)
L = Line(30)
M = Curve(180, 0, False)
N = Curve(0, 180, True)
J = Curve(90, 270, True)
S = Curve(270, 90, False)
S_T = Curve(270, 0, False)
S_P = Curve(270, 180, True)
T_S = Curve(0, 270, True)
W = Curve(180, 270, False)
S_N = Curve(0, 90, False)
K_R_S = Curve(90, 180, False)
S_K = Curve(90, 0, True)
O = Circle(0, 0, False)
DOWN_STEP = Space(270)
UP_STEP = Space(90)

DOT_1 = Schema(-1, H, 1, anchor=RELATIVE_1_ANCHOR)
DOT_2 = Schema(-1, H, 1, anchor=RELATIVE_2_ANCHOR)

SCHEMAS = [
    Schema(0x0020, SPACE, 260, TYPE.NON_JOINING, 260),
    Schema(0x00A0, SPACE, 260, TYPE.NON_JOINING, 260),
    Schema(0x0304, T, 0, anchor=ABOVE_ANCHOR),
    Schema(0x0307, H, 1, anchor=ABOVE_ANCHOR),
    Schema(0x0323, H, 1, anchor=BELOW_ANCHOR),
    Schema(0x2000, SPACE, 500, side_bearing=500),
    Schema(0x2001, SPACE, 1000, side_bearing=1000),
    Schema(0x2002, SPACE, 500, side_bearing=500),
    Schema(0x2003, SPACE, 1000, side_bearing=1000),
    Schema(0x2004, SPACE, 333, side_bearing=333),
    Schema(0x2005, SPACE, 250, side_bearing=250),
    Schema(0x2006, SPACE, 167, side_bearing=167),
    Schema(0x2007, SPACE, 572, side_bearing=572),
    Schema(0x2008, SPACE, 268, side_bearing=268),
    Schema(0x2009, SPACE, 200, side_bearing=200),
    Schema(0x200A, SPACE, 100, side_bearing=100),
    Schema(0x200B, SPACE, 2 * DEFAULT_SIDE_BEARING, side_bearing=0, default_ignorable=True),
    Schema(0x200C, SPACE, 0, TYPE.NON_JOINING, 0, default_ignorable=True),
    Schema(0x202F, SPACE, 200, side_bearing=200),
    Schema(0x205F, SPACE, 222, side_bearing=222),
    Schema(0x2060, SPACE, 2 * DEFAULT_SIDE_BEARING, side_bearing=0, default_ignorable=True),
    Schema(0xFEFF, SPACE, 2 * DEFAULT_SIDE_BEARING, side_bearing=0, default_ignorable=True),
    Schema(0x1BC00, H, 1),
    Schema(0x1BC02, P, 1),
    Schema(0x1BC03, T, 1),
    Schema(0x1BC04, F, 1),
    Schema(0x1BC05, K, 1),
    Schema(0x1BC06, L, 1),
    Schema(0x1BC07, P, 2),
    Schema(0x1BC08, T, 2),
    Schema(0x1BC09, F, 2),
    Schema(0x1BC0A, K, 2),
    Schema(0x1BC0B, L, 2),
    Schema(0x1BC0C, P, 3),
    Schema(0x1BC0D, T, 3),
    Schema(0x1BC0E, F, 3),
    Schema(0x1BC0F, K, 3),
    Schema(0x1BC10, L, 3),
    Schema(0x1BC11, T, 1, marks=[DOT_1]),
    Schema(0x1BC12, T, 1, marks=[DOT_2]),
    Schema(0x1BC13, T, 2, marks=[DOT_1]),
    Schema(0x1BC14, K, 1, marks=[DOT_2]),
    Schema(0x1BC15, K, 2, marks=[DOT_1]),
    Schema(0x1BC16, L, 1, marks=[DOT_1]),
    Schema(0x1BC17, L, 1, marks=[DOT_2]),
    Schema(0x1BC18, L, 2, marks=[DOT_1, DOT_2]),
    Schema(0x1BC19, M, 3),
    Schema(0x1BC1A, N, 3),
    Schema(0x1BC1B, J, 3),
    Schema(0x1BC1C, S, 3),
    Schema(0x1BC21, M, 3, marks=[DOT_1]),
    Schema(0x1BC22, N, 3, marks=[DOT_1]),
    Schema(0x1BC23, J, 3, marks=[DOT_1]),
    Schema(0x1BC24, J, 3, marks=[DOT_1, DOT_2]),
    Schema(0x1BC25, S, 3, marks=[DOT_1]),
    Schema(0x1BC26, S, 3, marks=[DOT_2]),
    Schema(0x1BC27, M, 4),
    Schema(0x1BC28, N, 4),
    Schema(0x1BC29, J, 4),
    Schema(0x1BC2A, S, 4),
    Schema(0x1BC2F, J, 4, marks=[DOT_1]),
    Schema(0x1BC32, S_T, 2),
    Schema(0x1BC33, S_T, 3),
    Schema(0x1BC34, S_P, 2),
    Schema(0x1BC35, S_P, 3),
    Schema(0x1BC36, T_S, 2),
    Schema(0x1BC37, T_S, 3),
    Schema(0x1BC38, W, 2),
    Schema(0x1BC39, W, 2, marks=[DOT_1]),
    Schema(0x1BC3A, W, 3),
    Schema(0x1BC3B, S_N, 2),
    Schema(0x1BC3C, S_N, 3),
    Schema(0x1BC3D, K_R_S, 2),
    Schema(0x1BC3E, K_R_S, 3),
    Schema(0x1BC3F, S_K, 2),
    Schema(0x1BC40, S_K, 3),
    Schema(0x1BC41, O, 1, TYPE.ORIENTING),
    Schema(0x1BC44, O, 2, TYPE.ORIENTING),
    Schema(0x1BC46, M, 1, TYPE.ORIENTING),
    Schema(0x1BC47, S, 1, TYPE.ORIENTING),
    Schema(0x1BC48, M, 1),
    Schema(0x1BC49, N, 1),
    Schema(0x1BC4A, J, 1),
    Schema(0x1BC4B, S, 1),
    Schema(0x1BC4C, S, 1, TYPE.ORIENTING, marks=[DOT_1]),
    Schema(0x1BC4D, S, 1, TYPE.ORIENTING, marks=[DOT_2]),
    Schema(0x1BC51, S_T, 1, TYPE.ORIENTING),
    Schema(0x1BC53, S_T, 1, TYPE.ORIENTING, marks=[DOT_1]),
    Schema(0x1BC5A, O, 2, TYPE.ORIENTING, marks=[DOT_1]),
    Schema(0x1BC65, S_P, 1, TYPE.ORIENTING),
    Schema(0x1BC66, W, 1, TYPE.ORIENTING),
    Schema(0x1BCA2, DOWN_STEP, 800, side_bearing=0, default_ignorable=True),
    Schema(0x1BCA3, UP_STEP, 800, side_bearing=0, default_ignorable=True),
]

def augment(font):
    add_lookups(font)
    return GlyphManager(font, SCHEMAS, PHASES).run()

