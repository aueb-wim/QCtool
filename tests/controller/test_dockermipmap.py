from __future__ import division
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import os
from pathlib import Path

import pytest

from mipqctool.controller.dockermipmap import DockerMipmap

FILE_PATH = os.path.abspath(os.path.dirname(__file__))
THISPATH = Path(FILE_PATH)
PARENTPATH = str(THISPATH.parent)

MAPPING1 = os.path.join(PARENTPATH, 'test_mapping', 'mapping')
SOURCE1 = os.path.join(PARENTPATH, 'test_mapping', 'source')
OUTPUT1 = os.path.join(PARENTPATH, 'test_mapping', 'output')
TARGET1 = os.path.join(PARENTPATH, 'test_mapping', 'target')


@pytest.mark.parametrize('mapping, source, target, output', [
    (MAPPING1, SOURCE1, TARGET1, OUTPUT1)
])
def test_dockermipmap(mapping, source, target, output):
    test = DockerMipmap(mapping, source, target, output)