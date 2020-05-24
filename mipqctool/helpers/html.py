# -*- coding: utf-8 -*-
# html.py

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals


from ..config import LOGGER
from jinja2 import Template

def tupples2table(pairs):
    """Returns an html table str
    Arguments:
    :param pairs: list of tupples, like dict.items()
    """
    html_text = """<table width="100%">
{% for pair in pairs %}
    <tr>
        <td>{{pair[0]}}</td>
        <td>{{pair[1]}}</td>
    </tr>
    {% endfor %}
</table>"""
    table_tpl = Template(html_text)
    return table_tpl.render(pairs=pairs)