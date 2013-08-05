# -*- coding: utf-8 -*-
# Smarty extension for Python-Markdown
# Author: 2013, Dmitry Shachnev <mitya57@gmail.com>

# SmartyPants license:
#
#   Copyright (c) 2003 John Gruber <http://daringfireball.net/>
#   All rights reserved.
#
#   Redistribution and use in source and binary forms, with or without
#   modification, are permitted provided that the following conditions are
#   met:
#
#   *  Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#
#   *  Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in
#      the documentation and/or other materials provided with the
#      distribution.
#
#   *  Neither the name "SmartyPants" nor the names of its contributors 
#      may be used to endorse or promote products derived from this
#      software without specific prior written permission.
#
#   This software is provided by the copyright holders and contributors "as
#   is" and any express or implied warranties, including, but not limited
#   to, the implied warranties of merchantability and fitness for a
#   particular purpose are disclaimed. In no event shall the copyright
#   owner or contributors be liable for any direct, indirect, incidental,
#   special, exemplary, or consequential damages (including, but not
#   limited to, procurement of substitute goods or services; loss of use,
#   data, or profits; or business interruption) however caused and on any
#   theory of liability, whether in contract, strict liability, or tort
#   (including negligence or otherwise) arising in any way out of the use
#   of this software, even if advised of the possibility of such damage.
#
#
# smartypants.py license:
#
#   smartypants.py is a derivative work of SmartyPants.
#   Copyright (c) 2004, 2007 Chad Miller <http://web.chad.org/>
#
#   Redistribution and use in source and binary forms, with or without
#   modification, are permitted provided that the following conditions are
#   met:
#
#   *  Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#
#   *  Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in
#      the documentation and/or other materials provided with the
#      distribution.
#
#   This software is provided by the copyright holders and contributors "as
#   is" and any express or implied warranties, including, but not limited
#   to, the implied warranties of merchantability and fitness for a
#   particular purpose are disclaimed. In no event shall the copyright
#   owner or contributors be liable for any direct, indirect, incidental,
#   special, exemplary, or consequential damages (including, but not
#   limited to, procurement of substitute goods or services; loss of use,
#   data, or profits; or business interruption) however caused and on any
#   theory of liability, whether in contract, strict liability, or tort
#   (including negligence or otherwise) arising in any way out of the use
#   of this software, even if advised of the possibility of such damage.

from __future__ import unicode_literals
from . import Extension
from ..inlinepatterns import HtmlPattern

def canonicalize(regex):
    """
    Converts the regexp from the re.VERBOSE form to the canonical form,
    i.e. remove all whitespace and ignore comments.
    """
    lines = regex.split('\n')
    for i in range(len(lines)):
        if ' #' in lines[i]:
            lines[i] = lines[i][:lines[i].find(' #')]
    return ''.join(lines).replace(' ', '')

# Constants for quote education.
punctClass = r"""[!"#\$\%'()*+,-.\/:;<=>?\@\[\\\]\^_`{|}~]"""
endOfWordClass = r"[\s.,;:!?)]"
closeClass = r"[^\ \t\r\n\[\{\(\-\u0002\u0003]"

openingQuotesBase = r"""
(
    \s            | # a whitespace char, or
    &nbsp;        | # a non-breaking space entity, or
    --            | # dashes, or
    –|—           | # unicode, or
    &[mn]dash;    | # named dash entities, or
    &#8211;|&#8212; # decimal entities
)
"""

# Special case if the very first character is a quote
# followed by punctuation at a non-word-break. Close the quotes by brute force:
singleQuoteStartRe = r"^'(?=%s\\B)" % punctClass
doubleQuoteStartRe = r'^"(?=%s\\B)' % punctClass

# Special case for double sets of quotes, e.g.:
#   <p>He said, "'Quoted' words in a larger quote."</p>
doubleQuoteSetsRe = r""""'(?=\w)"""
singleQuoteSetsRe = r"""'"(?=\w)"""

# Get most opening double quotes:
openingDoubleQuotesRegex = canonicalize("""
%s      # symbols before the quote
"       # the quote
(?=\w)  # followed by a word character
""" % openingQuotesBase)

# Double closing quotes:
closingDoubleQuotesRegex = canonicalize(r"""
"
(?=\s)
""")

closingDoubleQuotesRegex2 = canonicalize(r"""
(?<=%s)  # character that indicates the quote should be closing
"
""" % closeClass)

# Get most opening single quotes:
openingSingleQuotesRegex = canonicalize(r"""
%s      # symbols before the quote
'       # the quote
(?=\w)  # followed by a word character
""" % openingQuotesBase)

closingSingleQuotesRegex = canonicalize(r"""
(?<=%s)
'
(?!\s | s\b | \d)
""" % closeClass)

closingSingleQuotesRegex2 = canonicalize(r"""
(?<=%s)
'
(\s | s\b)
""" % closeClass)

# All remaining quotes should be opening ones
remainingSingleQuotesRegex = "'"
remainingDoubleQuotesRegex = '"'

lsquo, rsquo, ldquo, rdquo = '&lsquo;', '&rsquo;', '&ldquo;', '&rdquo;'

class SubstituteTextPattern(HtmlPattern):
    def __init__(self, pattern, replace, markdown_instance):
        """ Replaces matches with some text. """
        HtmlPattern.__init__(self, pattern)
        self.replace = replace
        self.markdown = markdown_instance

    def handleMatch(self, m):
        result = ''
        for part in self.replace:
            if isinstance(part, int):
                result += m.group(part)
            else:
                result += self.markdown.htmlStash.store(part, safe=True)
        return result

class SmartyExtension(Extension):
    def __init__(self, configs):
        self.config = {
            'smart_quotes': [True, 'Educate quotes'],
            'smart_dashes': [True, 'Educate dashes'],
            'smart_ellipses': [True, 'Educate ellipses']
        }
        for key, value in configs:
            if not isinstance(value, str):
                value = bool(value)
            elif value.lower() in ('true', 't', 'yes', 'y', '1'):
                value = True
            elif value.lower() in ('false', 'f', 'no', 'n', '0'):
                value = False
            else:
                raise ValueError('Cannot parse bool value: %s' % value)
            self.setConfig(key, value)

    def _addPatterns(self, md, patterns, serie):
        for ind, pattern in enumerate(patterns):
            pattern += (md,)
            pattern = SubstituteTextPattern(*pattern)
            after = ('>smarty-%s-%d' % (serie, ind - 1) if ind else '>entity')
            name = 'smarty-%s-%d' % (serie, ind)
            md.inlinePatterns.add(name, pattern, after)

    def educateDashes(self, md):
        emDashesPattern = SubstituteTextPattern(r'(?<!-)---(?!-)', '&mdash;', md)
        enDashesPattern = SubstituteTextPattern(r'(?<!-)--(?!-)', '&ndash;', md)
        md.inlinePatterns.add('smarty-em-dashes', emDashesPattern, '>entity')
        md.inlinePatterns.add('smarty-en-dashes', enDashesPattern,
            '>smarty-em-dashes')

    def educateEllipses(self, md):
        ellipsesPattern = SubstituteTextPattern(r'(?<!\.)\.{3}(?!\.)', '&hellip;', md)
        md.inlinePatterns.add('smarty-ellipses', ellipsesPattern, '>entity')

    def educateQuotes(self, md):
        patterns = (
            (singleQuoteStartRe, (rsquo,)),
            (doubleQuoteStartRe, (rdquo,)),
            (doubleQuoteSetsRe, (ldquo + lsquo,)),
            (singleQuoteSetsRe, (lsquo + ldquo,)),
            (openingSingleQuotesRegex, (2, lsquo)),
            (closingSingleQuotesRegex, (rsquo,)),
            (closingSingleQuotesRegex2, (rsquo, 2)),
            (remainingSingleQuotesRegex, (lsquo,)),
            (openingDoubleQuotesRegex, (2, ldquo)),
            (closingDoubleQuotesRegex, (rdquo,)),
            (closingDoubleQuotesRegex2, (rdquo,)),
            (remainingDoubleQuotesRegex, (ldquo,))
        )
        self._addPatterns(md, patterns, 'quotes')

    def extendMarkdown(self, md, md_globals):
        configs = self.getConfigs()
        if configs['smart_quotes']:
            self.educateQuotes(md)
        if configs['smart_dashes']:
            self.educateDashes(md)
        if configs['smart_ellipses']:
            self.educateEllipses(md)
        md.ESCAPED_CHARS.extend(['"', "'"])

def makeExtension(configs=None):
    return SmartyExtension(configs)
