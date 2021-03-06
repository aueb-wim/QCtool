from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json

from mipqctool.model.dcatalogue import Node, DcVariable
from mipqctool.config import LOGGER, DEFAULT_MISSING_VALUES


class FrictionlessFromDC(object):
    """This class is made for parsing a DC JSON metadata schema and creating
    its corresponding Frictionless descriptor dictionary.
    
    Arguments:
    :param dcjson: (dictionary) Data Catalogue specs schema 

    """
    __qcdescriptor = None

    def __init__(self, dcjson):
        # generates the tree structure of the loaded DC json
        LOGGER.info('Finding variable tree...')
        self.rootnode = Node(dcjson)
        self.__dc2qc()

    @property
    def total_variables(self):
        return len(self.rootnode.all_below_qcdesc)

    @property
    def qcdescriptor(self):
        return self.__qcdescriptor

    def save2frictionless(self, filepath):
        with open(filepath, 'w') as jsonfile:
            json.dump(self.__qcdescriptor, jsonfile)

    def __dc2qc(self):
        self.__qcdescriptor = {
            'fields': self.rootnode.all_below_qcdesc,
            'missingValues': DEFAULT_MISSING_VALUES
        }
