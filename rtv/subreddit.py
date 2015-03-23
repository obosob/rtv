import curses
import sys

import requests

from .exceptions import SubredditError
from .page import BasePage, Controller
from .submission import SubmissionPage
from .content import SubredditContent
from .helpers import clean, open_browser
from .curses_helpers import (BULLET, UARROW, DARROW, Color, LoadScreen,
                             text_input, show_notification)

__all__ = ['opened_links', 'SubredditController', 'SubredditPage']

# Used to keep track of browsing history across the current session
opened_links = set()

class SubredditController(Controller):
    """Controller for subreddit page."""
    character_map = {}

class SubredditPage(BasePage):

    def __init__(self, stdscr, reddit, name):

        self.controller = SubredditController(self)
        self.loader = LoadScreen(stdscr)

        content = SubredditContent.from_name(reddit, name, self.loader)
        super(SubredditPage, self).__init__(stdscr, reddit, content)

    def loop(self):

        while True:
            self._draw_page()
            cmd = self.stdscr.getch()
            self.controller.trigger(cmd)

    @SubredditController.register('r', curses.KEY_F5)
    def refresh_content(self, name=None):
        """
        Reset the content generator to force the subreddit to re-download.
        """
        name = name or self.content.name
        try:
            self.content = SubredditContent.from_name(
                self.reddit, name, self.loader)
        except SubredditError:
            show_notification(self.stdscr, ['Invalid subreddit'])
        except requests.HTTPError:
            show_notification(self.stdscr, ['Could not reach subreddit'])
        else:
            self.nav.page_index, self.nav.cursor_index = 0, 0
            self.nav.inverted = False

    @SubredditController.register('/')
    def prompt_subreddit(self):
        """
        Open a prompt to type in a new subreddit.
        """
        attr = curses.A_BOLD | Color.CYAN
        prompt = 'Enter Subreddit: /r/'
        n_rows, n_cols = self.stdscr.getmaxyx()
        self.stdscr.addstr(n_rows-1, 0, prompt, attr)
        self.stdscr.refresh()
        window = self.stdscr.derwin(1, n_cols-len(prompt),n_rows-1, len(prompt))
        window.attrset(attr)

        out = text_input(window)
        if out is not None:
            self.refresh_content(name=out)

    @SubredditController.register(curses.KEY_RIGHT, curses.KEY_ENTER, 'l')
    def open_submission(self):
        """
        Select the current submission to view posts.
        """
        global opened_links

        data = self.content.get(self.nav.absolute_index)
        page = SubmissionPage(self.stdscr, self.reddit, url=data['permalink'])
        page.loop()
        if data['url'] == 'selfpost':
            opened_links.add(data['url_full'])

    @SubredditController.register('o')
    def open_link(self):
        """
        Open the selected link in a webbrowser tab.
        """
        global opened_links

        url = self.content.get(self.nav.absolute_index)['url_full']
        open_browser(url)
        opened_links.add(url)

    @staticmethod
    def _draw_item(win, data, inverted=False):

        n_rows, n_cols = win.getmaxyx()
        n_cols -= 1  # Leave space for the cursor in the first column

        # Handle the case where the window is not large enough to fit the data.
        valid_rows = range(0, n_rows)
        offset = 0 if not inverted else -(data['n_rows'] - n_rows)

        n_title = len(data['split_title'])
        for row, text in enumerate(data['split_title'], start=offset):
            if row in valid_rows:
                text = clean(text)
                win.addnstr(row, 1, text, n_cols-1, curses.A_BOLD)

        row = n_title + offset
        if row in valid_rows:
            seen = (data['url_full'] in opened_links)
            link_color = Color.MAGENTA if seen else Color.BLUE
            attr = curses.A_UNDERLINE | link_color
            text = clean('{url}'.format(**data))
            win.addnstr(row, 1, text, n_cols-1, attr)

        row = n_title + offset + 1
        if row in valid_rows:
            text = clean('{score} '.format(**data))
            win.addnstr(row, 1, text, n_cols-1)

            if data['likes'] is None:
                text, attr = BULLET, curses.A_BOLD
            elif data['likes']:
                text, attr = UARROW, curses.A_BOLD | Color.GREEN
            else:
                text, attr = DARROW, curses.A_BOLD | Color.RED
            win.addnstr(text, n_cols-win.getyx()[1], attr)

            text = clean(' {created} {comments}'.format(**data))
            win.addnstr(text, n_cols-win.getyx()[1])

        row = n_title + offset + 2
        if row in valid_rows:
            text = clean('{author}'.format(**data))
            win.addnstr(row, 1, text, n_cols-1, curses.A_BOLD)
            text = clean(' {subreddit}'.format(**data))
            win.addnstr(text, n_cols-win.getyx()[1], Color.YELLOW)
            text = clean(' {flair}'.format(**data))
            win.addnstr(text, n_cols-win.getyx()[1], Color.RED)
