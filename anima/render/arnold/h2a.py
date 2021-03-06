# -*- coding: utf-8 -*-
# Copyright (c) 2012-2014, Anima Istanbul
#
# This module is part of anima-tools and is released under the BSD 2
# License: http://www.opensource.org/licenses/BSD-2-Clause

import os
import gzip
import struct
import time
import re

from anima.render.arnold import base85
reload(base85)

try:
    import hou
except ImportError:
    hou = None

from cStringIO import StringIO


class Buffer(object):
    """Buffer class for efficient string concatenation.

    This class uses cStringIO for the general store and a string buffer as an
    intermediate storage, then concatenates every 1000 element in to the
    cStringIO file handler.
    """

    def __init__(self, str_buffer_size=1000):
        self.i = 0
        self.str_buffer = []
        self.file_str = StringIO()
        self.file_str_write = self.file_str.write
        self.str_buffer_append = self.str_buffer.append
        self.str_buffer_size = str_buffer_size

    def flush(self):
        """flushes the data to the StringIO buffer and resets the counter
        """
        self.file_str_write(' '.join(self.str_buffer))
        self.str_buffer = []
        self.i = 0

    def append(self, data):
        """appends the data to the str_buffer if the limit is reached then the
        data in the buffer is flushed to the cStringIO
        """
        self_i = self.i
        self_i += 1
        if self_i == self.str_buffer_size:
            self.flush()
        self.str_buffer_append(`data`)

    def getvalue(self):
        """returns the string data
        """
        # do a last flush
        self.flush()
        return self.file_str.getvalue()


def geometry2ass(**kwargs):
    """exports geometry to ass format
    """
    ass_path = kwargs['path']
    name = kwargs['name']
    min_pixel_width = kwargs['min_pixel_width']
    mode = kwargs['mode']
    export_type = kwargs['export_type']
    export_motion = kwargs['export_motion']

    start_time = time.time()

    parts = os.path.splitext(ass_path)
    extension = parts[1]
    use_gzip = False
    if extension == '.gz':
        use_gzip = True
        basename = os.path.splitext(parts[0])[0]
    else:
        basename = parts[0]

    asstoc_path = '%s.asstoc' % basename

    node = hou.pwd()

    write_start = time.time()
    file_handler = open
    if use_gzip:
        file_handler = gzip.open

    # normalize path
    ass_path = os.path.normpath(ass_path)
    try:
        os.makedirs(os.path.dirname(ass_path))
    except OSError:  # path exists
        pass

    data = ''
    if export_type == 0:
        data = curves2ass(node, name, min_pixel_width, mode, export_motion)
    elif export_type == 1:
        data = polygon2ass(node, name, export_motion)

    ass_file = file_handler(ass_path, 'w')
    ass_file.write(data)
    ass_file.close()
    write_end = time.time()

    print('Writing to file            : %3.3f' % (write_end - write_start))

    node_inputs = node.inputs()
    try:
        second_input_geo = node_inputs[1].geometry()
    except IndexError:
        second_input_geo = None

    # use second input for bounding box if connected
    if export_motion and second_input_geo:
        bounding_box = second_input_geo.intrinsicValue('bounds')
    else:
        bounding_box = node.geometry().intrinsicValue('bounds')

    bounding_box_info = 'bounds %s %s %s %s %s %s' % (
        bounding_box[0], bounding_box[2], bounding_box[4],
        bounding_box[1], bounding_box[3], bounding_box[5]
    )

    with open(asstoc_path, 'w') as asstoc_file:
        asstoc_file.write(bounding_box_info)

    end_time = time.time()
    print('All Conversion took       : %3.3f sec' % (end_time - start_time))
    print('******************************************************************')


def polygon2ass(node, name, export_motion=False):
    """exports polygon geometry to ass format
    """
    sample_count = 2 if export_motion else 1

    geo = node.geometry()
    base_template = """
polymesh
{
 name %(name)s
 nsides %(primitive_count)i 1 UINT
%(number_of_points_per_primitive)s
 vidxs %(vertex_count)s 1 UINT
%(vertex_ids)s
 vlist %(point_count)s %(sample_count)s b85POINT
%(point_positions)s
 smoothing on
 visibility 65535
 sidedness 65535
 receive_shadows on
 self_shadows on
 matrix
%(matrix)s
 opaque on
 id 683108022
}"""
    #    """
    #polymesh
    #{
    # name %(name)s
    # nsides %(primitive_count)i %(sample_count)s UINT
    #  %(number_of_points_per_primitive)s
    # vidxs %(vertex_count) %(sample_count)s b85UINT
    #%(vertex_ids)s
    # uvidxs %(vertex_count)s %(sample_count)s b85UINT
    #%(uv_ids)s
    # vlist %(point_count) %(sample_count)s b85POINT
    #%(point_positions)s
    # nlist %(normal_count)s %(sample_count)s VECTOR
    #%(vertex_normals)s
    # uvlist %(vertex_count)s %(sample_count)s b85POINT2
    #%(uv_positions)s
    # smoothing on
    # visibility 65535
    # sidedness 65535
    # receive_shadows on
    # self_shadows on
    # matrix
    #%(matrix)s
    # opaque on
    # id 683108022
    #}
    #"""
    # skip attributes
    skip_normals = False
    skip_uvs = False

    intrinsic_values = geo.intrinsicValueDict()

    primitive_count = intrinsic_values['primitivecount']
    point_count = intrinsic_values['pointcount']
    vertex_count = intrinsic_values['vertexcount']

    number_of_points_per_primitive = []
    vertex_ids = []
    # vertex_normals = []

    # just for the first vertex try to read the uv to determine if we should
    # skip the uvs or not
    skip_uvs = True

    i = 0
    j = 0
    combined_vertex_ids = []
    # combined_vertex_normals = []
    combined_number_of_points_per_primitive = []

    for prim in geo.iterPrims():
        number_of_points_per_primitive.append(`prim.numVertices()`)
        i += 1
        if i > 500:
            i = 0
            combined_number_of_points_per_primitive.append(' '.join(number_of_points_per_primitive))
            number_of_points_per_primitive = []
        for vertex in prim.vertices():
            point = vertex.point()
            point_id = point.number()
            vertex_ids.append(`point_id`)
            # vertex_normals.extend(point.floatListAttribValue('N'))
            j += 1
            if j > 500:
                j = 0
                combined_vertex_ids.append(' '.join(vertex_ids))
                vertex_ids = []
                # combined_vertex_normals.append(' '.join(map(str, vertex_normals)))
                # vertex_normals = []

    # join for a last time
    if number_of_points_per_primitive:
        combined_number_of_points_per_primitive.append(' '.join(number_of_points_per_primitive))

    if vertex_ids:
        combined_vertex_ids.append(' '.join(vertex_ids))

    # if vertex_normals:
    #     combined_vertex_normals.append(' '.join(map(str, vertex_normals)))

    point_positions = geo.pointFloatAttribValuesAsString('P')

    if export_motion:
        point_prime_positions = geo.pointFloatAttribValuesAsString('pprime')
        point_positions = '%s%s' % (point_positions, point_prime_positions)

    # try:
    #    point_normals = geo.pointFloatAttribValuesAsString('N')
    #    # point_normals = geo.pointFloatAttribValues('N')
    # except hou.OperationFailed:
    #    # no normal attribute skip it
    #    skip_normals = True
    #    point_normals = ''

    #
    # Number Of Points Per Primitive
    #
    encode_start = time.time()
    #encoded_number_of_points_per_primitive = 'B%s' % base85.arnold_b85_encode(
    #    struct.pack(
    #        '>%sB' % len(number_of_points_per_primitive),
    #        *number_of_points_per_primitive
    #    )
    #)
    encoded_number_of_points_per_primitive = '\n'.join(combined_number_of_points_per_primitive)
    encode_end = time.time()
    print('Encoding Number of Points  : %3.3f' % (encode_end - encode_start))

    split_start = time.time()
    #splitted_number_of_points_per_primitive = \
    #    re.sub(
    #        "(.{500})", "\\1\n",
    #        #' '.join(number_of_points_per_primitive),
    #        encoded_number_of_points_per_primitive,
    #        0
    #    )
    #splitted_number_of_points_per_primitive = ' '.join(encoded_number_of_points_per_primitive)
    splitted_number_of_points_per_primitive = encoded_number_of_points_per_primitive
    split_end = time.time()
    print('Splitting Number of Points : %3.3f' % (split_end - split_start))


    #
    # Point Positions
    #
    encode_start = time.time()
    encoded_point_positions = base85.arnold_b85_encode(point_positions)
    encode_end = time.time()
    print('Encoding Point Position    : %3.3f' % (encode_end - encode_start))

    split_start = time.time()
    splitted_point_positions = re.sub("(.{500})", "\\1\n", encoded_point_positions, 0)
    split_end = time.time()
    print('Splitting Point Poisitions : %3.3f' % (split_end - split_start))

    # #
    # # Vertex Normals
    # #
    # encode_start = time.time()
    # encoded_vertex_normals = '\n'.join(combined_vertex_normals)#base85.arnold_b85_encode(point_normals)
    # encode_end = time.time()
    # print('Encoding Point Normals     : %3.3f' % (encode_end - encode_start))
    #
    # split_start = time.time()
    # # splitted_vertex_normals = re.sub("(.{500})", "\\1\n", encoded_point_normals, 0)
    # splitted_vertex_normals = encoded_vertex_normals
    # # # split every n-th data
    # # n = 100
    # # splitted_point_normals = []
    # # for i in range(len(point_normals) / n):
    # #     start_index = n * i
    # #     end_index = n * (i+1)
    # #     splitted_point_normals.extend(point_normals[start_index:end_index])
    # #     splitted_point_normals.append('\n')
    # #
    # # splitted_point_normals = ' '.join(map(str, splitted_point_normals))
    # split_end = time.time()
    # print('Splitting Vertex Normals    : %3.3f' % (split_end - split_start))

    #
    # Vertex Ids
    #
    encode_start = time.time()
    #encoded_vertex_ids = 'B%s' % base85.arnold_b85_encode(
    #    struct.pack(
    #        '>%sB' % len(vertex_ids),
    #        *vertex_ids
    #    )
    #)
    encoded_vertex_ids = '\n'.join(combined_vertex_ids)
    encode_end = time.time()
    print('Encoding Vertex Ids        : %3.3f' % (encode_end - encode_start))

    split_start = time.time()
    #splitted_vertex_ids = re.sub(
    #    "(.{500})", "\\1\n",
    #    #' '.join(vertex_ids),
    #    encoded_vertex_ids,
    #    0
    #)
    #splitted_vertex_ids = ' '.join(encoded_vertex_ids)
    splitted_vertex_ids = encoded_vertex_ids
    split_end = time.time()
    print('Splitting Vertex Ids       : %3.3f' % (split_end - split_start))

    matrix = """1 0 0 0
0 1 0 0
0 0 1 0
0 0 0 1
"""
    if export_motion:
        matrix += matrix

    data = base_template % {
        'name': name,
        'point_count': point_count,
        'vertex_count': vertex_count,
        'primitive_count': primitive_count,
        'sample_count': sample_count,
        'number_of_points_per_primitive': splitted_number_of_points_per_primitive,
        'vertex_ids': splitted_vertex_ids,
        'point_positions': splitted_point_positions,
        'matrix': matrix,
        # 'normal_count': vertex_count,
        # 'vertex_normals': splitted_vertex_normals,
        #'uv_ids': uv_ids,
        #'uv_positions': uv_positions
    }

    return data


def curves2ass(node, hair_name, min_pixel_width=0.5, mode='ribbon',
               export_motion=False):
    """exports the node content to ass file
    """
    sample_count = 2 if export_motion else 1
    template_vars = dict()
    geo = node.geometry()

    base_template = """
curves
{
 name %(name)s
 num_points %(curve_count)i %(sample_count)s UINT
  %(number_of_points_per_curve)s
 points %(point_count)s %(sample_count)s b85POINT
 %(point_positions)s

 radius %(radius_count)s %(sample_count)s b85FLOAT
 %(radius)s
 basis "catmull-rom"
 mode "%(mode)s"
 min_pixel_width %(min_pixel_width)s
 visibility 65535
 receive_shadows on
 self_shadows on
 matrix 1 %(sample_count)s MATRIX
  %(matrix)s
 opaque on
 declare uparamcoord uniform FLOAT
 uparamcoord %(curve_count)i %(sample_count)s b85FLOAT
 %(uparamcoord)s
 declare vparamcoord uniform FLOAT
 vparamcoord %(curve_count)i %(sample_count)s b85FLOAT
 %(vparamcoord)s
 declare curve_id uniform UINT
 curve_id %(curve_count)i %(sample_count)s UINT
  %(curve_ids)s
}
"""

    number_of_curves = geo.intrinsicValue('primitivecount')
    real_point_count = geo.intrinsicValue('pointcount')

    # The root and tip points are going to be used twice for the start and end tangents
    # so there will be 2 extra points per curve
    point_count = real_point_count + number_of_curves * 2

    # write down the radius for the tip twice
    radius_count = real_point_count

    real_number_of_points_in_one_curve = real_point_count / number_of_curves
    number_of_points_in_one_curve = real_number_of_points_in_one_curve + 2
    number_of_points_per_curve = [`number_of_points_in_one_curve`] * number_of_curves

    curve_ids = ' '.join(`id_` for id_ in xrange(number_of_curves))

    radius = None

    pack = struct.pack

    # try to find the width as a point attribute to speed things up
    getting_radius_start = time.time()
    radius_attribute = geo.findPointAttrib('width')
    if radius_attribute:
        # this one works 100 times faster then iterating over each vertex
        radius = geo.pointFloatAttribValuesAsString('width')
    else:
        # no radius in points, so iterate over each vertex
        radius_i = 0
        radius_str_buffer = []
        radius_file_str = StringIO()
        radius_file_str_write = radius_file_str.write
        radius_str_buffer_append = radius_str_buffer.append
        for prim in geo.prims():
            prim_vertices = prim.vertices()

            # radius
            radius_i += real_number_of_points_in_one_curve
            if radius_i >= 1000:
                radius_file_str_write(''.join(radius_str_buffer))
                radius_str_buffer = []
                radius_str_buffer_append = radius_str_buffer.append
                radius_i = 0

            for vertex in prim_vertices:
                radius_str_buffer_append(pack('f', vertex.attribValue('width')))

        # do flushes again before getting the values
        radius_file_str_write(''.join(radius_str_buffer))
        radius = radius_file_str.getvalue()
    getting_radius_end = time.time()
    print('Getting Radius Info        : %3.3f' %
          (getting_radius_end - getting_radius_start))

    # point positions
    encode_start = time.time()

    # for motion blur use pprime
    getting_point_positions_start = time.time()
    point_positions = geo.pointFloatAttribValuesAsString('P')

    if export_motion:
        point_prime_positions = geo.pointFloatAttribValuesAsString('pprime')
        point_positions = '%s%s' % (point_positions, point_prime_positions)

    getting_point_positions_end = time.time()
    print('Getting Point Position     : %3.3f' %
          (getting_point_positions_end - getting_point_positions_start))

    # repeat every first and last point coordinates
    # (3 value each 3 * 4 = 12 characters) of every curve
    zip_start = time.time()
    point_positions = ''.join(
        map(
            lambda x: '%s%s%s' % (x[:12], x, x[-12:]),
            map(
                ''.join,
                zip(*[iter(point_positions)] * (real_number_of_points_in_one_curve*4*3)))
        )
    )
    zip_end = time.time()
    print('Zipping Point Position     : %3.3f' % (zip_end - zip_start))

    encoded_point_positions = base85.arnold_b85_encode(point_positions)
    encode_end = time.time()
    print('Encoding Point Position    : %3.3f' % (encode_end - encode_start))

    split_start = time.time()
    splitted_point_positions = re.sub("(.{500})", "\\1\n", encoded_point_positions, 0)
    split_end = time.time()
    print('Splitting Point Positions  : %3.3f' % (split_end - split_start))

    # radius
    encode_start = time.time()
    encoded_radius = base85.arnold_b85_encode(radius)
    encode_end = time.time()
    print('Radius encode              : %3.3f' % (encode_end - encode_start))

    split_start = time.time()
    splitted_radius = re.sub("(.{500})", "\\1\n", encoded_radius, 0)
    # extend for motion blur
    if export_motion:
        splitted_radius = '%(data)s%(data)s' % {'data': splitted_radius}
    split_end = time.time()
    print('Splitting Radius           : %3.3f' % (split_end - split_start))

    # uv
    getting_uv_start = time.time()
    u = geo.primFloatAttribValuesAsString('uv_u')
    v = geo.primFloatAttribValuesAsString('uv_v')
    getting_uv_end = time.time()
    print('Getting uv                 : %3.3f' %
          (getting_uv_end - getting_uv_start))

    encode_start = time.time()
    encoded_u = base85.arnold_b85_encode(u)
    encode_end = time.time()
    print('Encoding UParamcoord       : %3.3f' % (encode_end - encode_start))

    split_start = time.time()
    splitted_u = re.sub("(.{500})", "\\1\n", encoded_u, 0)
    if export_motion:
        splitted_u = '%(data)s%(data)s' % {'data': splitted_u}
    split_end = time.time()
    print('Splitting UParamCoord      : %3.3f' % (split_end - split_start))

    encode_start = time.time()
    encoded_v = base85.arnold_b85_encode(v)
    encode_end = time.time()
    print('Encoding VParamcoord       : %3.3f' % (encode_end - encode_start))

    split_start = time.time()
    splitted_v = re.sub("(.{500})", "\\1\n", encoded_v, 0)
    if export_motion:
        splitted_v = '%(data)s%(data)s' % {'data': splitted_v}
    split_end = time.time()
    print('Splitting VParamCoord      : %3.3f' % (split_end - split_start))

    print('len(encoded_point_positions) : %s' % len(encoded_point_positions))
    print('(p + 2 * c) * 5 * 3          : %s' % (point_count * 5 * 3))
    print('len(encoded_radius)          : %s' % len(encoded_radius))
    print('len(uv)                      : %s' % len(u))
    print('len(encoded_u)               : %s' % len(encoded_u))
    print('len(encoded_v)               : %s' % len(encoded_v))

    # extend for motion blur
    matrix = """1 0 0 0
  0 1 0 0
  0 0 1 0
  0 0 0 1
"""
    if export_motion:
        number_of_points_per_curve.extend(number_of_points_per_curve)
        matrix += matrix

    template_vars.update({
        'name': node.path().replace('/', '_'),
        'curve_count': number_of_curves,
        'real_point_count': real_point_count,
        'number_of_points_per_curve': ' '.join(number_of_points_per_curve),
        'point_count': point_count,
        'point_positions': splitted_point_positions,
        'radius': splitted_radius,
        'radius_count': radius_count,
        'curve_ids': curve_ids,
        'uparamcoord': splitted_u,
        'vparamcoord': splitted_v,
        'min_pixel_width': min_pixel_width,
        'mode': mode,
        'sample_count': sample_count,
        'matrix': matrix
    })

    rendered_curve_data = base_template % template_vars

    return rendered_curve_data
