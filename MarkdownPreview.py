# -*- encoding: UTF-8 -*-
import sublime
import sublime_plugin

import os
import sys
import tempfile
import re
import json
import urllib2

import desktop
import markdown2

def getTempMarkdownPreviewPath(view):
    ''' return a permanent full path of the temp markdown preview file '''

    settings = sublime.load_settings('MarkdownPreview.sublime-settings')

    tmp_filename = '%s.html' % view.id()
    if settings.get('path_tempfile'):
        tmp_fullpath = os.path.join(settings.get('path_tempfile'), tmp_filename)
    else:
        tmp_fullpath = os.path.join(tempfile.gettempdir(), tmp_filename)
    return tmp_fullpath

def save_utf8(filename, text):
    v = sublime.version()
    if v >= '3000':
        f = open(filename, 'w', encoding='utf-8')
        f.write(text)
        f.close()
    else: # 2.x
        f = open(filename, 'w')
        f.write(text.encode('utf-8'))
        f.close()

def load_utf8(filename):
    v = sublime.version()
    if v >= '3000':
        return open(filename, 'r', encoding='utf-8').read()
    else: # 2.x
        return open(filename, 'r').read().decode('utf-8')


def load_resource(name):
    ''' return file contents for files within the package root folder '''
    v = sublime.version()
    if v >= '3000':
        try:
            filename = 'Packages/Markdown Preview/'+name
            return sublime.load_resource(filename)
        except:
            return ''
    else: # 2.x
        filename = os.path.join(sublime.packages_path(), 'Markdown Preview', name)

        if os.path.isfile(filename):
            return open(filename, 'r').read().decode('utf-8')
        else:
            filename = os.path.join(sublime.packages_path(), 'sublimetext-markdown-preview', name) ## why is this ?
            if os.path.isfile(filename):
                return open(filename, 'r').read().decode('utf-8')
            return ''

def new_scratch_view(window, text):
    ''' create a new scratch view and paste text content
        return the new view
    '''

    new_view = window.new_file()
    new_view.set_scratch(True)
    if sublime.version() >= '3000':
        new_view.run_command('append', {
            'characters': text,
        })
    else: # 2.x
        new_edit = new_view.begin_edit()
        new_view.insert(new_edit, 0, text)
        new_view.end_edit(new_edit)
    return new_view

class MarkdownPreviewListener(sublime_plugin.EventListener):
    ''' auto update the output html if markdown file has already been converted once '''

    def on_post_save(self, view):
        settings = sublime.load_settings('MarkdownPreview.sublime-settings')
        filetypes = settings.get('markdown_filetypes')
        if filetypes and view.file_name().endswith(tuple(filetypes)):
            temp_file = getTempMarkdownPreviewPath(view)
            if os.path.isfile(temp_file):
                # reexec markdown conversion
                view.run_command('markdown_preview', {'target': 'disk'})
                sublime.status_message('Markdown preview file updated')


class MarkdownCheatsheetCommand(sublime_plugin.TextCommand):
    ''' open our markdown cheat sheet in ST2 '''
    def run(self, edit):
        lines = '\n'.join(load_resource('sample.md').splitlines())
        view = new_scratch_view(self.view.window(), lines)
        view.set_name("Markdown Cheatsheet")
        try:
            view.set_syntax_file("Packages/Markdown/Markdown.tmLanguage")
        except:
            pass
        sublime.status_message('Markdown cheat sheet opened')


class MarkdownPreviewCommand(sublime_plugin.TextCommand):
    ''' preview file contents with python-markdown and your web browser '''

    def getCSsOnSearchPath(self):
        css_name = self.settings.get('css', 'default')
        if os.path.isabs(css_name):
            return u"<link href='%s' rel='stylesheet' type='text/css'>" % css_name

        if css_name == 'default':
            css_name = 'github.css' if self.settings.get('parser', 'default') == 'github' else 'markdown.css'

        # Try the local folder for css file.
        mdfile = self.view.file_name()
        if mdfile is not None:
            css_path = os.path.join(os.path.dirname(mdfile), css_name)
            if os.path.isfile(css_path):
                return u"<style>%s</style>" % load_utf8(css_path)

        # Try the build-in css files.
        return u"<style>%s</style>" % load_resource(css_name)

    def getOverrideCSS(self):
        ''' handls allow_css_overrides setting. '''

        if self.settings.get('allow_css_overrides'):
            filename = self.view.file_name()
            filetypes = self.settings.get('markdown_filetypes')

            if filename and filetypes:
                for filetype in filetypes:
                    if filename.endswith(filetype):
                        css_filename = filename.rpartition(filetype)[0] + '.css'
                        if (os.path.isfile(css_filename)):
                            return u"<style>%s</style>" % load_utf8(css_filename)
        return ''

    def getCSS(self):
        ''' return the correct CSS file based on parser and settings '''
        return self.getCSsOnSearchPath() + self.getOverrideCSS()

    def getMathJax(self):
        ''' return the MathJax script if enabled '''

        if self.settings.get('enable_mathjax') is True:
            return load_resource('mathjax.html')
        return ''

    def getHighlight(self):
        ''' return the Highlight.js and css if enabled '''

        highlight = ''
        if self.settings.get('enable_highlight') is True and self.settings.get('parser') == 'default':
            highlight += "<style>%s</style>" % load_resource('highlight.css')
            highlight += "<script>%s</script>" % load_resource('highlight.js')
            highlight += "<script>hljs.initHighlightingOnLoad();</script>"
        return highlight


    def get_contents(self, region):
        ''' Get contents or selection from view and optionally strip the YAML front matter '''
        contents = self.view.substr(region)
        # use selection if any
        selection = self.view.substr(self.view.sel()[0])
        if selection.strip() != '':
            contents = selection
        if self.settings.get('strip_yaml_front_matter') and contents.startswith('---'):
            title = ''
            title_match = re.search('(?:title:)(.+)', contents, flags=re.IGNORECASE)
            if title_match:
                stripped_title = title_match.group(1).strip()
                title = '%s\n%s\n\n' % (stripped_title, '=' * len(stripped_title))
            contents_without_front_matter = re.sub(r'(?s)^---.*---\n', '', contents)
            contents = '%s%s' % (title, contents_without_front_matter)
        return contents

    def postprocessor(self, html):
        ''' fix relative paths in images, scripts, and links for the internal parser '''
        def tag_fix(match):
            tag, src = match.groups()
            filename = self.view.file_name()
            if filename:
                if not src.startswith(('file://', 'https://', 'http://', '/', '#')):
                    abs_path = u'file://%s/%s' % (os.path.dirname(filename), src)
                    tag = tag.replace(src, abs_path)
            return tag
        RE_SOURCES = re.compile("""(?P<tag><(?:img|script|a)[^>]+(?:src|href)=["'](?P<src>[^"']+)[^>]*>)""")
        html = RE_SOURCES.sub(tag_fix, html)
        return html

    def get_config_extensions(self, default_extensions):
        config_extensions = self.settings.get('enabled_extensions')
        if not config_extensions or config_extensions == 'default':
            return default_extensions
        if 'default' in config_extensions:
            config_extensions.remove( 'default' )
            config_extensions.extend( default_extensions )
        return config_extensions

    def convert_markdown(self, markdown_text):
        ''' convert input markdown to HTML, with github or builtin parser '''
        config_parser = self.settings.get('parser')
        github_oauth_token = self.settings.get('github_oauth_token')

        markdown_html = u'cannot convert markdown'
        if config_parser and config_parser == 'github':
            # use the github API
            sublime.status_message('converting markdown with github API...')
            try:
                github_mode = self.settings.get('github_mode', 'gfm')
                data = {
                    "text": markdown_text,
                    "mode": github_mode
                }
                headers = {
                    'Content-Type': 'application/json'
                }
                if github_oauth_token:
                    headers['Authorization'] = "token %s" % github_oauth_token
                data = json.dumps(data).encode('utf-8')
                url = "https://api.github.com/markdown"
                sublime.status_message(url)
                request = urllib2.Request(url, data, headers)
                markdown_html = urllib2.urlopen(request).read().decode('utf-8')
            except urllib2.HTTPError, e:
                if e.code == 401:
                    sublime.error_message('github API auth failed. Please check your OAuth token.')
                else:
                    sublime.error_message('github API responded in an unfashion way :/')
            except urllib2.URLError:
                sublime.error_message('cannot use github API to convert markdown. SSL is not included in your Python installation')
            except:
                sublime.error_message('cannot use github API to convert markdown. Please check your settings.')
            else:
                sublime.status_message('converted markdown with github API successfully')
        else:
            # convert the markdown
            enabled_extras = set(self.get_config_extensions(['footnotes', 'toc', 'fenced-code-blocks', 'cuddled-lists']))
            if self.settings.get("enable_mathjax") is True or self.settings.get("enable_highlight") is True:
                enabled_extras.add('code-friendly')
            markdown_html = markdown2.markdown(markdown_text, extras=list(enabled_extras))
            toc_html = markdown_html.toc_html
            if toc_html:
                toc_markers = ['[toc]', '[TOC]', '<!--TOC-->']
                for marker in toc_markers:
                    markdown_html = markdown_html.replace(marker, toc_html)

            # postprocess the html from internal parser
            markdown_html = self.postprocessor(markdown_html)

        return markdown_html

    def get_title(self):
        title = self.view.name()
        if not title:
            fn = self.view.file_name()
            title = 'untitled' if not fn else os.path.splitext(os.path.basename(fn))[0]
        return '<title>%s</title>' % title

    def run(self, edit, target='browser'):
        self.settings = sublime.load_settings('MarkdownPreview.sublime-settings')
        region = sublime.Region(0, self.view.size())

        contents = self.get_contents(region)

        markdown_html = self.convert_markdown(contents)

        full_html = u'<!DOCTYPE html>'
        full_html += '<html><head><meta charset="utf-8">'
        full_html += self.getCSS()
        full_html += self.getHighlight()
        full_html += self.getMathJax()
        full_html += self.get_title()
        full_html += '</head><body>'
        full_html += markdown_html
        full_html += '</body>'
        full_html += '</html>'

        if target in ['disk', 'browser']:
            # check if LiveReload ST2 extension installed and add its script to the resulting HTML
            livereload_installed = ('LiveReload' in os.listdir(sublime.packages_path()))
            # build the html
            if livereload_installed:
                full_html += '<script>document.write(\'<script src="http://\' + (location.host || \'localhost\').split(\':\')[0] + \':35729/livereload.js?snipver=1"></\' + \'script>\')</script>'
            # update output html file
            tmp_fullpath = getTempMarkdownPreviewPath(self.view)
            save_utf8(tmp_fullpath, full_html)
            # now opens in browser if needed
            if target == 'browser':
                config_browser = self.settings.get('browser')
                if config_browser and config_browser != 'default':
                    cmd = '"%s" %s' % (config_browser, tmp_fullpath)
                    if sys.platform == 'darwin':
                        cmd = "open -a %s" % cmd
                    elif sys.platform == 'linux2':
                        cmd += ' &'
                    result = os.system(cmd)
                    if result != 0:
                        sublime.error_message('cannot execute "%s" Please check your Markdown Preview settings' % config_browser)
                    else:
                        sublime.status_message('Markdown preview launched in %s' % config_browser)
                else:
                    desktop.open(tmp_fullpath)
                    sublime.status_message('Markdown preview launched in default html viewer')
        elif target == 'sublime':
            # create a new buffer and paste the output HTML
            new_scratch_view(self.view.window(), markdown_html)
            sublime.status_message('Markdown preview launched in sublime')
        elif target == 'clipboard':
            # clipboard copy the full HTML
            sublime.set_clipboard(full_html)
            sublime.status_message('Markdown export copied to clipboard')
