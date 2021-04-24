# -*- coding: utf-8 -*-
# ColumnReport.py

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import platform
from collections import namedtuple, OrderedDict

# for testing htlm2pdf columnreport template
from jinja2 import Environment, FileSystemLoader
if platform.system() != 'Windows':
    from weasyprint import HTML

from mipqctool.qcfrictionless import QcField
from mipqctool import config, qctypes
from mipqctool.config import LOGGER, PRETTY_STAT_NAMES
from mipqctool.exceptions import DataTypeError, ConstraintViolationError
from mipqctool.helpers.html import list2parag, tupples2table

config.debug(True)


class ColumnReport(object):
    """This class is used to hold statistical and validation data of values
    of a dataset column.
    """
    def __init__(self, raw_values, qcfield, threshold=3, **options):
        """Arguments:
        :param raw_values: list of strings representing values of a column
        :param qcfield: QcField object
        :param threshold: outlier threshold - (mean - threshold * std, mean + threshold * std) 
                          outside this length, a numerical value is considered outlier
        """

        self.__threshold = threshold
        # Stores all the values of the column in a list of
        # tupples (row number, raw value)
        self.__raw_pairs = enumerate(raw_values, start=1)
        self.__corrected = False

        self.__stats = {}
        self.__total_rows = len(raw_values)
        self.__not_nulls = 0
        self.__null_total = 0
        self.__null_rows = None
        self.__not_null_rows = None
        # list of tupples that have been validated
        self.__validated_pairs = []
        # list of tupples that have been corrected
        self.__corrected_pairs = []
        self.__datatype_violated_pairs = []
        self.__constraint_violated_pairs = []
        self.__dsuggestions = None
        self.__csuggestions = None
        # stats about datatype, constraint violations and
        # suggested corrections
        self.__success_total_d = 0
        self.__success_total_c = 0
        self.__failed_total_d = 0
        self.__failed_total_c = 0
        # Create QcField object and other relative variables
        # and functions
        self.__field = qcfield
        self.__miptype = self.__field.miptype
        self.__profile = self.__get_profile_function()
        self.__cast_value = self.__field.cast_value
        self.__missing_values = self.__field.missing_values

    @property
    def qcfield(self):
        """Returns the object QcField"""
        return self.__field

    @property
    def name(self):
        return self.qcfield.name

    @property
    def miptype(self):
        return self.__miptype

    @property
    def total_rows(self):
        return self.__total_rows

    @property
    def datatype_errors(self):
        """Total datatype violations"""
        return len(self.__datatype_violated_pairs)

    @property
    def constraint_errors(self):
        """Total constraint violations"""
        return len(self.__constraint_violated_pairs)

    @property
    def stats(self):
        """Statistics dictionary, different keys per qctype"""
        return self.__stats
    @property
    def value_range(self):
        """Value range derived from stats."""
        if self.miptype == 'nominal':
            return self.stats['categories']
        elif self.miptype in ['integer', 'numerical']:
            return [self.stats['min'], self.stats['max']]


    @property
    def invalid_rows(self):
        """set of row numbers with violations"""
        vrows = set([pair[0] for pair
                     in self.__constraint_violated_pairs])
        vrows.update([pair[0] for pair
                      in self.__datatype_violated_pairs])
        return vrows

    @property
    def valid_rows(self):
        """set of row numbers with valid data"""
        validrows = set([pair[0] for pair
                         in self.__validated_pairs])
        if self.__corrected:
            validrows.update([pair[0] for pair
                              in self.__corrected_pairs])
        return validrows

    @property
    def nulls_total(self):
        """Total number of rows with nulls"""
        return self.__null_total

    @property
    def not_nulls_total(self):
        """Total number of rows with no nulls"""
        return self.__not_nulls_total

    @property
    def null_row_numbers(self):
        """Set of row numbers with nulls"""
        return set(self.__null_rows)

    @property
    def filled_row_numbers(self):
        """Set of row numbers filled with valid values"""
        return set(self.__not_null_rows)

    @property
    def corrected(self):
        """Are the violation corrections applied?"""
        return self.__corrected

    @property
    def dcorrections(self):
        """Returns the datatype corrections as set of (original, corrected)."""
        null = self.__missing_values[0]
        correctiontupples = [(sug[1], sug[2])
                             for sug in self.__dsuggestions
                             if sug[2] != null]
        return set(correctiontupples)

    @property
    def dnulls(self):
        """Returns the values with datatype vialations unable to correct."""
        null = self.__missing_values[0]
        values = [sug[1]
                  for sug in self.__dsuggestions
                  if sug[2] == null]
        return set(values)

    @property
    def ccorrections(self):
        "Returns the constraint corrections as set of (original, corrected)."
        null = self.__missing_values[0]
        correctiontupples = [(sug[1], sug[2])
                             for sug in self.__csuggestions
                             if sug[2] != null]
        return set(correctiontupples)

    @property
    def cnulls(self):
        """Returns the values with constraint vialations unable to correct."""
        null = self.__missing_values[0]
        values = [sug[1]
                  for sug in self.__csuggestions
                  if sug[2] == null]
        return set(values)

    @property
    def corrected_values(self):
        if self.__corrected:
            pairs = sorted(self.__validated_pairs + self.__corrected_pairs,
                           key=lambda tup: tup[0])
            return [pair[1] for pair in pairs]
        else:
            return None


    @property
    def filledpercentage(self):
        return round(self.not_nulls_total / self.total_rows * 100, 2)

    @property
    def prettygeneral(self):
        """Returns a dict with row stats with readable keys"""
        dictrows = OrderedDict()
        dictrows['Type'] = self.miptype
        dictrows['Total number of rows'] = self.total_rows
        dictrows['Number of rows with data'] = self.not_nulls_total
        dictrows['Completion percentage'] = str(self.filledpercentage) + '%'
        dictrows['Number of rows with constraint violations'] = self.constraint_errors
        dictrows['Number of rows with datatype violations'] = self.datatype_errors
        if self.__corrected:
            dictrows['Data Cleansing applied?'] = 'Yes'
            dictrows['Number of successful correction attempts of constraint violations'] = self.__success_total_c
            dictrows['Number of successful correction attempts of datatype violations'] = self.__success_total_d
            dictrows['Total number of violations replaced by null'] = self.__failed_total_c + self.__failed_total_d
        else:
            dictrows['Data Cleansing applied?'] = 'No'

        return dictrows

    @property
    def prettystats(self, decimals=3):
        prettydict = OrderedDict()
        for key in self.stats.keys():
            pretty_key = PRETTY_STAT_NAMES.get(key, key)
            value = self.stats[key]
            if isinstance(value, float):
                value = round(value, decimals)
            prettydict[pretty_key] = value
        return prettydict

    def validate(self):
        """Search for datatype and constraint violations."""
        for raw_pair in self.__raw_pairs:
            try:
                self.__field.validate(raw_pair[1])
                self.__validated_pairs.append(raw_pair)
            except DataTypeError:
                self.__datatype_violated_pairs.append(raw_pair)
                continue
            except ConstraintViolationError:
                self.__constraint_violated_pairs.append(raw_pair)
                continue
        self.__suggest_corrections()
        self.__calc_stats()
        return True

    def apply_corrections(self):
        """Apply the suggested corrections for both types of violations"""
        # NOTE corrections may include null values as suggestions
        datatypes = [(sd.row, sd.newvalue) for sd in self.__dsuggestions]
        constraints = [(sc.row, sc.newvalue) for sc in self.__csuggestions]
        self.__corrected_pairs = datatypes + constraints
        self.__corrected = True
        self.__calc_stats()

    def printpdf(self, filepath):
        app_path = os.path.abspath(os.path.dirname(__file__))
        env_path = os.path.join(app_path, 'html')
        css_path = os.path.join(env_path, 'style.css')
        env = Environment(loader=FileSystemLoader(env_path))
        template = env.get_template('column_report.html')
        if self.__corrected:
            status = 'Applied'
            null_replaced = 'have been'
        else:
            status = 'Suggested'
            null_replaced = 'will be'
        template_vars = {
            'cname': self.qcfield.name,
            'gen_stat_table': tupples2table(self.prettygeneral.items()),
            'stat_table': tupples2table(self.prettystats.items()),
            'status': status,
            'null_replaced': null_replaced,
            'dcorrections_table': tupples2table(self.dcorrections),
            'ccorrections_table': tupples2table(self.ccorrections),
            'removed_values': list2parag(self.cnulls | self.dnulls),
        }
        html_out = template.render(template_vars)
        document = HTML(string=html_out).render(stylesheets=[css_path])
        document.write_pdf(target=filepath)

    def to_html(self):
        app_path = os.path.abspath(os.path.dirname(__file__))
        env_path = os.path.join(app_path, 'html')
        env = Environment(loader=FileSystemLoader(env_path))
        template = env.get_template('column_report.html')
        if self.__corrected:
            status = 'Applied'
            null_replaced = 'have been'
        else:
            status = 'Suggested'
            null_replaced = 'will be'
        template_vars = {
            'cname': self.qcfield.name,
            'gen_stat_table': tupples2table(self.prettygeneral.items()),
            'stat_table': tupples2table(self.prettystats.items()),
            'status': status,
            'null_replaced': null_replaced,
            'dcorrections_table': tupples2table(self.dcorrections),
            'ccorrections_table': tupples2table(self.ccorrections),
            'removed_values': list2parag(self.cnulls | self.dnulls),
        }
        return template.render(template_vars)


    # Private
    def __get_profile_function(self):
        return getattr(qctypes, 'profile_%s' % self.miptype)

    def __suggestd(self, value):
        """Suggest a new value in case of datatype violation.
        Arguments:
        :param value: string
        :returns: string
        """
        null_string = self.__missing_values[0]
        suggested_value = self.__field.suggestd(value)
        if suggested_value != null_string:
            self.__success_total_d += 1
        else:
            self.__failed_total_d += 1

        return suggested_value

    def __suggestc(self, value):
        """Suggest a new value in case of constraint violation.
        Arguments:
        :param value: string
        :returns: string
        """
        null_string = self.__missing_values[0]
        suggested_value = self.__field.suggestc(value)
        if suggested_value != null_string:
            self.__success_total_c += 1
        else:
            self.__failed_total_c += 1

        return suggested_value

    def __reset_sugg_stats(self):
        self.__success_total_d = 0
        self.__success_total_c = 0
        self.__failed_total_d = 0
        self.__failed_total_c = 0

    def __calc_stats(self):
        """Calcs statistics about the valid values."""
        profiler = self.__get_profile_function()
        raw_pairs = self.__validated_pairs + self.__corrected_pairs
        casted_pairs = []
        rows_with_nulls = []
        rows_with_no_nulls = []
        total_rows_with_nulls = 0
        for pair in raw_pairs:
            casted_value = self.__field.cast_value(pair[1])
            if casted_value:
                casted_pairs.append((pair[0], casted_value))
                rows_with_no_nulls.append(pair[0])
            else:
                rows_with_nulls.append(pair[0])
                total_rows_with_nulls += 1
        if len(casted_pairs) == 0:
            # all values are null
            stats = {}
        else:
            stats = profiler(casted_pairs, threshold=self.__threshold)
        self.__not_nulls_total = len(casted_pairs)
        self.__null_total = total_rows_with_nulls
        self.__null_rows = rows_with_nulls
        self.__not_null_rows = rows_with_no_nulls
        self.__stats = stats

    def __suggest_corrections(self):
        """Try to suggest corrections for the violeted values."""
        self.__reset_sugg_stats()
        Suggestion = namedtuple('Suggestion', 'row, value, newvalue')
        dsuggestions = [Suggestion(row=pair[0],
                                   value=pair[1],
                                   newvalue=self.__suggestd(pair[1]))
                        for pair in self.__datatype_violated_pairs]

        csuggestions = [Suggestion(row=pair[0],
                                   value=pair[1],
                                   newvalue=self.__suggestc(pair[1]))
                        for pair in self.__constraint_violated_pairs]
        self.__dsuggestions = dsuggestions
        self.__csuggestions = csuggestions
