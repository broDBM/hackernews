#!/usr/bin/env python

import argparse, os, pickle, re, requests
from pyquery import PyQuery as pq
import pystache

BASE_PATH = os.path.dirname(__file__)
COOKIE = os.path.join(BASE_PATH, 'hackernews.cookie')
EXPORT_TYPES = ( 'json', 'xml', )


def _login(**kwargs):
    """Log in to Hacker News and return the cookies."""

    if 'r' not in kwargs:
        # We haven't established a login request.

        # If we're using cookies, try to return those instead.
        if not kwargs['args'].no_cookies:

            # If the cookie doesn't exist, create it.
            try:
                cookie = open(COOKIE, 'r')
            except IOError:
                cookie = open(COOKIE, 'w')

            # If there's something in the cookie, return that.
            if os.stat(COOKIE).st_size:
                cookies = pickle.load(cookie)
                cookie.close()
                return cookies
            else:
                cookie.close()

        # Request a blank login page to harvest the fnid (a CSRF-type key).
        r = requests.get('https://news.ycombinator.com/newslogin')
        J = pq(r.content)
        fnid = J('input[name="fnid"]').val()

        # Build the login POST data and make the login request.
        payload = {
            'fnid': fnid,
            'u': kwargs['args'].username,
            'p': kwargs['args'].password,
        }
        r = requests.post('https://news.ycombinator.com/y', data=payload)

        cookies = r.cookies

    else:
        # Set the cookies to the cached login request's cookies.
        cookies = kwargs['r'].cookies

    # Set the cookie
    if not kwargs['args'].no_cookies:
        cookie = open(COOKIE, 'w+')
        pickle.dump(cookies, cookie)
        cookie.close()

    return cookies

def _reset_cookie():
    cookie = open(COOKIE, 'rw')
    cookie.truncate(0)
    cookie.close()

def _good_response(**kwargs):

    # Handle an invalid cookie / login.
    if kwargs['r'].content == "Can't display that.":
        _reset_cookie()
        return False

    return True


def _get_saved_stories(**kwargs):
    """Returns a sorted list of the user's saved stories."""

    # Log in to get cookies.
    cookies = _login(**kwargs)

    if 'r' not in kwargs:
        # This is the first saved items request.
        # Make the saved items request and set an empty list.
        kwargs['r'] = requests.get('http://news.ycombinator.com/saved?id=%s' % kwargs['args'].username,
                                   cookies=cookies)

        if not _good_response(**kwargs):
            return _get_saved_stories(**kwargs)

        kwargs['saved'] = []

    # Grab the stories.
    J = pq(kwargs['r'].content)
    stories = J('table table td.title')

    for story in stories:
        title = J(story).text()

        # Skip digit-only <td>s and the 'More' link.
        if not re.match('\d+\.|More', title):

            url = J('a', story).attr('href')

            # For HN links, make absolute URL.
            if not url.startswith('http'):
                url = 'https://news.ycombinator.com/' + url

            # Add the story to the saved list.
            kwargs['saved'].append({
                'title': title,
                'url': url,
            })

    # If we're getting all saved stories.
    if kwargs['args'].all:

        # Find the 'More' link and load it.
        last = J('a', J('table table tr td.title:last'))
        if last.text() == 'More':
            kwargs['r'] = requests.get('https://news.ycombinator.com%s' % last.attr('href'),
                                       cookies=cookies)

            # Check to make sure we have a good response.
            _good_response(**kwargs)

            # Call this function again, this time with the new list.
            return _get_saved_stories(**kwargs)

    return kwargs['saved']

def saved(args):
    """Returns a formatted list of the logged-in user's saved stories."""

    stories = _get_saved_stories(args=args)

    if args.export == 'json':
        return stories
    elif args.export == 'xml':
        return pystache.render("""<?xml version="1.0" encoding="utf-8"?>
            <feed xmlns="http://www.w3.org/2005/Atom">
                <title>Saved stories on Hacker News</title>
                {{#stories}}
                <entry>
                    <title>{{title}}</title>
                    <link href="{{url}}" />
                </entry>
                {{/stories}}
            </feed>""", {'stories': stories})

if __name__ == '__main__':

    # Parser
    parser = argparse.ArgumentParser(prog='Hacker News')
    parser.add_argument('--version', action='version', version='%(prog)s 0.1')
    subparsers = parser.add_subparsers()

    # Subparsers
    saved_parser = subparsers.add_parser('saved')
    saved_parser.add_argument('-u', '--username', dest='username', help='HN Username',
                              required=True)
    saved_parser.add_argument('-p', '--password', dest='password', help='HN Password',
                              required=True)
    saved_parser.add_argument('-e', '--export', dest='export', help='Export type',
                              required=False, default='json', choices=EXPORT_TYPES)
    saved_parser.add_argument('--all', dest='all', help='Get all saved stories',
                              action='store_true')
    saved_parser.add_argument('--no-cookies', dest='no_cookies', help="Don't save cookies",
                              action='store_true', default=False)
    saved_parser.set_defaults(func=saved)

    # Args
    args = parser.parse_args()
    print args.func(args)
