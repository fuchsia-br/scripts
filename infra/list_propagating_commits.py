#!/usr/bin/env python
# Copyright 2017 The Fuchsia Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import base64
import json
import requests
import sys
import xml.etree.ElementTree as xml


LAYERS = [
    'topaz',
    'peridot',
    'garnet',
    'zircon',
]


def get_lower_layer(layer):
    """Returns the layer immediately below the given layer."""
    index = LAYERS.index(layer)
    if index == len(LAYERS) - 1:
        return None
    return LAYERS[index + 1]


def get_lower_layer_commit(layer, at):
    """Returns the pinned revision of the layer below the given layer."""
    lower_layer = get_lower_layer(layer)
    if not lower_layer:
        return (None, None)
    url = ('https://fuchsia.googlesource.com/%s/+/%s/manifest/%s?format=TEXT'
           % (layer, at, layer))
    content = requests.get(url).content
    content = base64.b64decode(content)
    manifest = xml.fromstring(content)
    nodes = manifest.findall('./imports/import[@name="%s"]' % lower_layer)
    return (lower_layer, nodes[0].get('revision'))


def get_commits(layer, revision):
    """Returns the commits in the given layer up to a given commit."""
    url = 'https://fuchsia.googlesource.com/%s/+log/master?format=JSON' % layer
    def get_more(result, start=None):
        get_url = url
        if start:
            get_url = '%s&s=%s' % (url, start)
        content = requests.get(url).content
        # Remove the anti-XSSI header.
        content = content[5:]
        data = json.loads(content)
        for commit in data['log']:
            if commit['commit'] == revision:
                return
            result.append(commit)
        get_more(result, start=content['next'])
    result = []
    get_more(result)
    return result


def filter_commit(commit):
    """Returns True if a commit should be listed."""
    author = commit['author']['name']
    if author == 'skia-deps-roller@chromium.org':
        return False
    for layer in LAYERS:
        if author == '%s-roller' % layer:
            return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--layer',
                        help='Name of the layer to inspect',
                        choices=LAYERS,
                        required=True)
    args = parser.parse_args()
    layer = args.layer
    revision = 'master'

    while True:
        (lower_layer, lower_revision) = get_lower_layer_commit(layer, revision)
        if not lower_layer:
            return
        commits = get_commits(lower_layer, lower_revision)
        commits = [c for c in commits if filter_commit(c)]
        print('')
        print('        --------------')
        print('        | %s |' % '{:^10}'.format(lower_layer))
        print('        --------------')
        for commit in commits:
            print('%s | %s | %s' % (commit['commit'][:7],
                                    commit['author']['name'][:15].ljust(15),
                                    commit['message'].splitlines()[0]))
        if not commits:
            print('None')
        layer = lower_layer
        revision = lower_revision

    return 0


if __name__ == "__main__":
    sys.exit(main())