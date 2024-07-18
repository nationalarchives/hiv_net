#!/usr/bin/env python3

import os
import json
import argparse
import requests

parser = argparse.ArgumentParser()
parser.add_argument('query')
parser.add_argument('--force', '-f', action = 'store_true', help = 'Refetch data, even if a cache exists')
parser.add_argument('--key', '-k', help = 'Either an API key, or a file containing the API key')
parser.add_argument('--cache', default = 'cache', help = 'Directory of cache files')
parser.add_argument('--no-cache', action = 'store_true', help = 'Do not cache anything (implies --force)')
args = parser.parse_args()
if os.path.exists(args.key):
  with open(args.key) as f:
    args.key = f.read().rstrip('\n').strip()
if not os.path.exists(args.cache):
  os.makedirs(args.cache)
if args.no_cache: args.force = True

headers = {
  'X-ELS-APIKey': args.key,
}
params = {
  'query': args.query,
}
SCOPUS_SEARCH='https://api.elsevier.com/content/search/scopus'

if (not(args.force)) and os.path.exists(f'{args.cache}/1.json'):
  with open(f'{args.cache}/1.json') as f:
    data = json.load(f)
else:
  #TODO: Deal with multiple pages
  try: #re https://stackoverflow.com/a/16511493
    resp = requests.get(SCOPUS_SEARCH, headers = headers, params = params)
    resp.raise_for_status()
  except requests.exceptions.RequestException as e:
    raise SystemExit(e)
  data = resp.json()
  if not args.no_cache:
    with open(f'{args.cache}/1.json', 'w') as f:
      json.dump(data, f, indent = 2)

entries = data['search-results']['entry']
print(f'Found {len(entries)} 1st-level citers')
for entry in entries:
  if 'eid' in entry:
    print(entry['eid'])
  else:
    print('DOH')


