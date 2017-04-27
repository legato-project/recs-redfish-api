# Copyright Notice:
# Copyright 2016 Distributed Management Task Force, Inc. All rights reserved.
# License: BSD 3-Clause License. For full text see link: https://github.com/DMTF/Redfish-Tools/LICENSE.md

"""
File : dokuwiki_generator.py

Brief : This file contains definitions for the DokuwikiGenerator class.

Initial author: Second Rise LLC.
"""

import math
from . import DocFormatter

class DokuwikiGenerator(DocFormatter):
    """Provides methods for generating dokuwiki content from Redfish schemas.
    """


    def __init__(self, property_data, traverser, config):
        super(DokuwikiGenerator, self).__init__(property_data, traverser, config)
        self.sections = []
        self.separators = {
            'inline': ', ',
            'linebreak': '\n'
            }
        self.dokuwiki_separators = {
            'whitespace': '\ ',
            'linebreak': '\\\\ '
            }
        self.schema_link_basepath = 'documentation:redfish_api:schema_definition#'
        #self.endpoint_link_basepath = 'documentation:redfish_api:endpoints:'
        
        schema_filename = config['outfile']
        self.intro_filename = schema_filename.replace('.schema.', '.main.')


    def parse_property_info(self, schema_name, prop_name, traverser, prop_infos, current_depth):
        """Parse a list of one more more property info objects into strings for display.

        Returns a dict of 'prop_type', 'read_only', descr', 'prop_is_object',
        'prop_is_array', 'object_description', 'prop_details', 'item_description',
        'has_direct_prop_details'
        """

        if len(prop_infos) == 1:
            prop_info = prop_infos[0]
            if isinstance(prop_info, dict):
                return self._parse_single_property_info(schema_name, prop_name, prop_info, current_depth)
            else:
                return self.parse_property_info(schema_name, prop_name, prop_info, current_depth)

        parsed = {'prop_type': [],
                  'prop_units': False,
                  'prop_pattern': False,
                  'prop_format': False,
                  'prop_min': False,
                  'prop_max': False,
                  'read_only': False,
                  'descr': [],
                  'prop_is_object': False,
                  'prop_is_array': False,
                  'prop_is_nullable': False,
                  'object_description': [],
                  'item_description': [],
                  'prop_details': {},
                  'has_direct_prop_details': False}

        anyOf_details = [self.parse_property_info(schema_name, prop_name, traverser, x, current_depth) for x in prop_infos]

        # Remove details for anyOf props with prop_type = 'null'.
        details = []
        has_null = False
        for det in anyOf_details:
            if len(det['prop_type']) == 1 and 'null' in det['prop_type']:
                has_null = True
            else:
                details.append(det)

        # Uniquify these properties and save as lists:
        props_to_combine = ['prop_type', 'descr', 'object_description', 'item_description']

        for property_name in props_to_combine:
            property_values = []
            for det in anyOf_details:
                if isinstance(det[property_name], list):
                    for val in det[property_name]:
                        if val and val not in property_values:
                            property_values.append(val)
                else:
                    val = det[property_name]
                    if val and val not in property_values:
                        property_values.append(val)

            parsed[property_name] = property_values

        # add back null if we found one:
        if has_null:
            parsed['prop_is_nullable'] = True
            parsed['prop_type'].append('null')

        # read_only and units should be the same for all
        parsed['read_only'] = details[0]['read_only']
        parsed['prop_units'] = details[0]['prop_units']
        parsed['prop_pattern'] = details[0]['prop_pattern']
        parsed['prop_format'] = details[0]['prop_format']
        parsed['prop_min'] = details[0]['prop_min']
        parsed['prop_max'] = details[0]['prop_max']

        for det in details:
            parsed['prop_is_object'] |= det['prop_is_object']
            parsed['prop_is_array'] |= det['prop_is_array']
            parsed['has_direct_prop_details'] |= det['has_direct_prop_details']
            parsed['prop_details'].update(det['prop_details'])

        return parsed


    def _parse_single_property_info(self, schema_name, prop_name, prop_info, current_depth):
        """Parse definition of a specific property into strings for display.

        Returns a dict of 'prop_type', 'prop_units', 'read_only', descr', 'prop_is_object',
        'prop_is_array', 'object_description', 'prop_details', 'item_description',
        'has_direct_prop_details'
        """

        traverser = self.traverser

        # type may be a string or a list.
        prop_details = {}
        prop_type = prop_info.get('type', [])
        prop_is_object = False; object_description = ''
        prop_is_array = False; item_description = ''
        has_prop_details = False

        if isinstance(prop_type, list):
            prop_is_object = 'object' in prop_type
            prop_is_array = 'array' in prop_type
        else:
            prop_is_object = prop_type == 'object'
            prop_is_array = prop_type == 'array'
            prop_type = [ prop_type ]

        prop_units = prop_info.get('units')
        prop_pattern = prop_info.get('pattern')
        prop_format = prop_info.get('format')
        prop_min = prop_info.get('minimum')
        prop_max = prop_info.get('maximum')

        read_only = prop_info.get('readonly')
        if self.config['normative'] and 'longDescription' in prop_info:
            descr = prop_info.get('longDescription', '')
        else:
            descr = prop_info.get('description', '')

        # Items, if present, will have a definition with either an object or a $ref:
        prop_item = prop_info.get('items')
        if isinstance(prop_item, dict):
            prop_items = self.extend_property_info(schema_name, prop_item, traverser)

        # Enumerations go into Property Details
        prop_enum = prop_info.get('enum')
        supplemental_details = None

        if 'supplemental' in self.config and 'Property Details' in self.config['supplemental']:
            detconfig = self.config['supplemental']['Property Details']
            if schema_name in detconfig and prop_name in detconfig[schema_name]:
                supplemental_details = detconfig[schema_name][prop_name]

        if prop_enum or supplemental_details:
            has_prop_details = True

            if self.config['normative'] and 'enumLongDescriptions' in prop_info:
                prop_enum_details = prop_info.get('enumLongDescriptions')
            else:
                prop_enum_details = prop_info.get('enumDescriptions')
            prop_details[prop_name] = self.format_property_details(prop_name, prop_type, prop_enum, prop_enum_details,
                                                              supplemental_details)

        # embedded object:
        if current_depth < self.max_drilldown and prop_is_object:
            object_formatted = self.format_object_description(schema_name, prop_info, traverser, current_depth)
            object_description = object_formatted['rows']
            if object_formatted['details']:
                prop_details.update(object_formatted['details'])

        # embedded items:
        if current_depth < self.max_drilldown and prop_is_array:
            item_formatted = self.format_list_of_object_descriptions(schema_name, prop_items, traverser, current_depth)
            item_description = item_formatted['rows']
            if item_formatted['details']:
                prop_details.update(item_formatted['details'])

        return {'prop_type': prop_type,
                'prop_units': prop_units,
                'prop_pattern': prop_pattern,
                'prop_format': prop_format,
                'prop_min': prop_min,
                'prop_max': prop_max,
                'read_only': read_only,
                'descr': descr,
                'prop_is_object': prop_is_object,
                'prop_is_array': prop_is_array,
                'object_description': object_description,
                'item_description': item_description,
                'prop_details': prop_details,
                'has_direct_prop_details': has_prop_details}


    def format_property_row(self, schema_name, prop_name, prop_info, meta=None, current_depth=0):
        """Format information for a single property. Returns an object with 'row' and 'details'.

        'row': content for the main table being generated.
        'details': content for the Property Details section.

        This may include embedded objects with their own properties.
        """

        traverser = self.traverser
        formatted = []     # The row itself
        indentation_string = self.dokuwiki_separators['whitespace'] * 6 * current_depth

        if not meta:
            meta = {}

        formatted_details = self.parse_property_info(schema_name, prop_name, traverser, prop_info, current_depth)

        # Eliminate dups in these these properties and join with a delimiter:
        props = {
            'prop_type': self.separators['inline'],
            'descr': self.separators['linebreak'],
            'object_description': self.separators['linebreak'],
            'item_description': self.separators['linebreak']
            }
        
        for property_name, delim in props.items():
            if isinstance(formatted_details[property_name], list):
                property_values = []
                for val in formatted_details[property_name]:
                    if val and val not in property_values:
                        property_values.append(val)
                formatted_details[property_name] = delim.join(property_values)
                
        name_and_version = '**' + self.escape_for_dokuwiki(prop_name, self.config['escape_chars']) + '**'

        if formatted_details['prop_is_object']:
            if formatted_details['object_description'] == '':
                name_and_version += ' {}'
            else:
                name_and_version += ' {'

        if formatted_details['prop_is_array']:
            if formatted_details['item_description'] == '':
                name_and_version += ' [ {} ]'
            else:
                name_and_version += ' [ {'


        if formatted_details['prop_units']:
            formatted_details['descr'] += self.dokuwiki_separators['linebreak'] + 'unit: ' + formatted_details['prop_units']
        if formatted_details['prop_pattern']:
            formatted_details['descr'] += self.dokuwiki_separators['linebreak'] + 'pattern: ' + formatted_details['prop_pattern']
        if formatted_details['prop_format']:
            formatted_details['descr'] += self.dokuwiki_separators['linebreak'] + 'format: ' + formatted_details['prop_format']
        if formatted_details['prop_min']:
            formatted_details['descr'] += self.dokuwiki_separators['linebreak'] + 'minimum: ' + str(formatted_details['prop_min'])
        if formatted_details['prop_max']:
            formatted_details['descr'] += self.dokuwiki_separators['linebreak'] + 'maximum: ' + str(formatted_details['prop_max'])

        # If there are prop_details (enum details), add a note to the description:
        if formatted_details['has_direct_prop_details']:
            formatted_details['descr'] += self.dokuwiki_separators['linebreak'] + '//See Property Details, below, for more information about this property.//'


        prop_type = formatted_details['prop_type']

        prop_perm = ''
        if formatted_details['read_only']:
            prop_perm = 'read-only'
        else:
            prop_perm = 'read-write'
        

        row = []
        row.append(indentation_string + name_and_version)
        row.append(prop_type)
        row.append(prop_perm)
        row.append(formatted_details['descr'])

        formatted.append('| ' + ' | '.join(row) + ' |')

        if len(formatted_details['object_description']) > 0:
            formatted.append(formatted_details['object_description'])
            formatted.append('| ' + indentation_string + '} |   |   |')

        if len(formatted_details['item_description']) > 0:
            formatted.append(formatted_details['item_description'])
            formatted.append('| ' + indentation_string + '} ] |   |   |')

        return({'row': '\n'.join(formatted), 'details':formatted_details['prop_details']})


    def format_property_details(self, prop_name, prop_type, enum, enum_details, supplemental_details):
        """Generate a formatted table of enum information for inclusion in Property Details."""

        contents = []
        contents.append('== ' + prop_name + ' ==\n')

        if isinstance(prop_type, list):
            prop_type = ', '.join(prop_type)

        if supplemental_details:
            contents.append('\n' + supplemental_details + '\n')

        if enum_details:
            contents.append('^ ' + prop_type + ' ^ Description ^')
            enum.sort()
            for enum_item in enum:
                contents.append('| ' + enum_item + ' | ' + enum_details.get(enum_item, '') + ' |')

        elif enum:
            contents.append('^ ' + prop_type + ' ^')
            for enum_item in enum:
                contents.append('| ' + enum_item + ' | ')

        return '\n'.join(contents) + '\n'


    def format_list_of_object_descriptions(self, schema_name, prop_items, traverser, current_depth):
        """Format a (possibly nested) list of embedded objects.

        We expect this to amount to one definition, usually for 'items' in an array."""

        if isinstance(prop_items, dict):
            return self.format_object_description(schema_name, prop_items, traverser, current_depth)

        rows = []
        details = {}
        if isinstance(prop_items, list):
            for prop_item in prop_items:
                formatted = self.format_list_of_object_descriptions(schema_name, prop_item, traverser, current_depth)
                rows.extend(formatted['rows'])
                details.update(formatted['details'])
            return ({'rows': rows, 'details': details})

        return None

    def write_intro_file(self):
        """ Output contents for intro site """

        contents = []
        
        contents.append('===== Schema Definition =====\n')
        
        contents.append('<WRAP group><WRAP quarter column>')

        i = 1
        num_sections = len(self.sections)
        quarter = math.ceil(num_sections / 4)
        
        for section in self.sections:
            section_name = self.escape_for_dokuwiki(section['head'], self.config['escape_chars'])
            contents.append('  * [[' + self.schema_link_basepath + section_name.lower() + '|' + section_name + ']]')
            if i % quarter == 0 and i < num_sections:
                contents.append('</WRAP><WRAP quarter column>')
            i += 1
        
        contents.append('</WRAP></WRAP>\n')
        
        self.write_to_file(self.separators['linebreak'].join(contents), self.intro_filename)
        

    def emit(self):
        """ Output contents thus far """

        contents = []
        
        contents.append('\n====== Schema Definition ======\n')

        for section in self.sections:
            contents.append(section['heading'])
            if section['description']:
                contents.append(section['description'])
            if section['json_payload']:
                contents.append(section['json_payload'])
            # something is awry if there are no properties, but ...
            if section['properties']:
                contents.append('^ Property ^ Type ^ Permission ^ Description ^')
                contents.append('\n'.join(section['properties']))
            if section['property_details']:
                contents.append('\n=== Property Details ===\n')
                contents.append('\n'.join(section['property_details']))

        return self.separators['linebreak'].join(contents)


    def output_document(self):
        """Return full contents of document"""
        
        self.write_intro_file()
        
        return self.emit()


    def add_section(self, text):
        """ Add a top-level heading """
        text = text.split(' ')[0]
        self.this_section = {'head': text,
                             'heading': '\n===== ' + text + ' =====\n',
                             'properties': [],
                             'property_details': []
                             }

        self.sections.append(self.this_section)


    def add_description(self, text):
        """ Add the schema description """
        self.this_section['description'] = text + '\n'


    def add_json_payload(self, json_payload):
        """ Add a JSON payload for the current section """
        if json_payload:
            self.this_section['json_payload'] = '\n' + json_payload + '\n'
        else:
            self.this_section['json_payload'] = None


    def add_property_row(self, formatted_text):
        """Add a row (or group of rows) for an individual property in the current section/schema.

        formatted_row should be a chunk of text already formatted for output"""
        self.this_section['properties'].append(formatted_text)


    def add_property_details(self, formatted_details):
        """Add a chunk of property details information for the current section/schema."""
        self.this_section['property_details'].append(formatted_details)


    @staticmethod
    def escape_for_dokuwiki(text, chars):
        """Escape selected characters in text to prevent auto-formatting in dokuwiki."""
        for char in chars:
            text = text.replace(char, '\\' + char)
        return text
    
    @staticmethod
    def write_to_file(content, outfile_name):
        """Write content to a file."""
        
        try:
            outfile = open(outfile_name, 'w')
            print(content, file=outfile)
        except (OSError) as ex:
            print('Unable to open', outfile_name, 'to write:', ex)
        outfile.close()
        
        print(outfile_name, "written.")

