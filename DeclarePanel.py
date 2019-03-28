# -*- coding: utf-8 -*-
# @Author: maxst
# @Date:   2019-03-23 10:38:30
# @Last Modified by:   Max ST
# @Last Modified time: 2019-03-28 12:08:31
import sublime
import sublime_plugin

try:
    from Anaconda.commands import AnacondaGoto as ParentResult
except (ImportError):
    ParentResult = sublime_plugin.TextCommand


class BufferResult(object):
    __slots__ = ('results', 'symbol', 'status')
    __instance = None
    START = 1
    DONE = 2
    HOLD = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.clean()

    def __str__(self):
        return '{0} "{1}" {2}'.format('BufferResult', self.symbol, self.results)

    def clean(self):
        self.results = []
        self.symbol = ''
        self.status = self.HOLD

    def is_loading(self):
        return self.status == self.START

    @classmethod
    def get_instance(cls):
        if not cls.__instance:
            cls.__instance = BufferResult()
        return cls.__instance


class GotoResult(ParentResult):
    def run(self, edit, *args, **kwargs):
        self.settings = sublime.load_settings("DeclarePanel.sublime-settings")
        self.buffer = BufferResult.get_instance()
        self.buffer.status = self.buffer.START
        ignored_packages = self.view.settings().get('ignored_packages', [])

        if all((
                self.settings.get('use_anaconda', True),
                hasattr(self, 'JEDI_COMMAND'),
                'Anaconda' not in ignored_packages,
        )):
            super().run(edit)
        else:
            self.on_success({'result': None})

    def on_success(self, data):
        """Called when a result comes from the query
        """
        if not data.get('result'):
            if self.buffer.symbol:
                self.buffer.results = self.view.window().lookup_symbol_in_index(self.buffer.symbol)
        else:
            for result in data['result']:
                path = self._infere_context_data(result[1])
                self.buffer.results.append((path, path.split('/')[-1], (result[2], result[3])))
                break
        self.buffer.status = self.buffer.DONE


class DeclarePanelCommand(sublime_plugin.WindowCommand):

    NAME_PANEL = 'DeclarePanel'
    NAME_REGION = 'region_declare'

    def run(self, *args, **kwargs):
        self.settings = sublime.load_settings("DeclarePanel.sublime-settings")
        self.view = self.window.active_view()
        if kwargs.get('show_panel', False):
            return self.show_panel()
        self.buffer = BufferResult.get_instance()
        self.buffer.clean()
        self.buffer.symbol = self.get_symbol()
        self.search(self.buffer.symbol)

    def get_symbol(self):
        sel = self.view.sel()[0]
        sel = self.view.word(sel) if sel.empty() else sel
        return self.view.substr(sel).strip()

    def search(self, symbol):
        def async_search():
            handle_results(self.buffer.results)

        def handle_results(results):
            if results:
                self.print_symbol(results[0])
            else:
                sublime.status_message('Symbol "{0}" not found'.format(symbol))

        self.window.run_command('goto_result')
        self.run_after_loading(self.buffer, async_search)

    def print_symbol(self, result):
        source = ''
        if result[0].lower() == self.view.file_name().lower():
            source = self.view.substr(sublime.Region(0, self.view.size()))
        else:
            with open(result[0]) as file:
                source = ''.join(file.readlines()).strip('\n')

        self.print_to_panel(source, *result)

    def description(self):
        return 'DecPanel: Show declare\talt+s'

    def run_after_loading(self, view, func):
        """Run a function after the view has finished loading"""

        def run():
            if view.is_loading():
                sublime.set_timeout(run, 10)
            else:
                # add an additional delay, because it might not be ready
                # even if the loading function returns false
                sublime.set_timeout(func, 10)

        run()

    def print_to_panel(self, text, path=None, file_name=None, line_col=(0, 0), region_mark=None):
        self.kill_panel()
        panel = self.window.create_output_panel(self.NAME_PANEL, False)
        panel.set_read_only(False)
        panel.run_command('append', {'characters': text})
        panel.set_syntax_file(self.view.settings().get('syntax'))

        def show_at_center():
            panel.sel().clear()
            panel.sel().add(declar_point)
            panel.show_at_center(show_point)

        if sum(line_col) > 0:
            row, col = line_col

            if self.settings.get('highlight_declare', True):
                region_mark = panel.word(panel.text_point(line_col[0] - 1, line_col[1]))
                panel.add_regions(self.NAME_REGION, [region_mark], 'string', 'dot', sublime.DRAW_NO_FILL)

            show_point = panel.text_point(row - 1, 0)
            declar_point = panel.text_point(row - 1, col - 1)
            self.run_after_loading(panel, show_at_center)

        panel.set_read_only(True)
        self.show_panel(panel)

    def kill_panel(self):
        self.window.destroy_output_panel(self.NAME_PANEL)

    def show_panel(self, panel=None):
        panel_view = self.window.find_output_panel(self.NAME_PANEL) if not panel else panel
        if panel_view:
            self.window.run_command('show_panel', {'panel': 'output.{0}'.format(self.NAME_PANEL), "toggle": True})
            self.window.focus_view(panel_view)
            if self.settings.get('scroll_toggle', True):
                for reg in panel_view.get_regions(self.NAME_REGION):
                    panel_view.show_at_center(reg)
                    break
