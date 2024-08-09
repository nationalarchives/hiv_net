#!/usr/bin/env python3

import os
import sys
import json
import pyvis
import inflect
import argparse
import requests
import pandas as pd
import networkx as nx

def get_citations(title, eid):
  headers = {
    'X-ELS-APIKey': args.key,
  }
  SCOPUS_SEARCH='https://api.elsevier.com/content/search/scopus'

  if (not args.force) and os.path.exists(f'{args.cache}/{eid}.json'):
      with open(f'{args.cache}/{eid}.json') as f:
        data = json.load(f)
  else:
    #TODO: Deal with multiple pages
    try: #re https://stackoverflow.com/a/16511493
      resp = requests.get(SCOPUS_SEARCH, headers = headers, params = { 'query': f'REF({title})' })
      resp.raise_for_status()
      data = resp.json()
    except requests.exceptions.RequestException as e:
      if args.fail_on_error:
        raise SystemExit(e)
      else:
        print(e, file = sys.stderr)
        data = { 'fail': str(e) }

    if not args.no_cache:
      with open(f'{args.cache}/{eid}.json', 'w') as f:
        json.dump(data, f, indent = 2)

  return data

i_engine = inflect.engine()
parser = argparse.ArgumentParser()
parser.add_argument('title')
parser.add_argument('--force', '-f', action = 'store_true', help = 'Refetch data, even if a cache exists')
parser.add_argument('--key', '-k', help = 'Either an API key, or a file containing the API key')
parser.add_argument('--cache', default = 'cache', help = 'Directory of cache files')
parser.add_argument('--no-cache', action = 'store_true', help = 'Do not cache anything (implies --force)')
parser.add_argument('--depth', '-d', default = 3, type = int, help = 'Depth of citation')
parser.add_argument('--fail-on-error', action = 'store_true', help = 'Fail on error, instead of logging')
parser.add_argument('--verbose', action = 'store_true')
args = parser.parse_args()
if os.path.exists(args.key):
  with open(args.key) as f:
    args.key = f.read().rstrip('\n').strip()
if not os.path.exists(args.cache):
  os.makedirs(args.cache)
if args.no_cache: args.force = True

#outer list index indicates depth of citation
#dictionary key indicates source being cited
#dictionary value is list of citers of the key
works = [
  {0: get_citations(args.title, 0)}, #Key 0 is a false EID for our starting point
]

repeats = [{}]
for d in range(1, args.depth):
  next_repeats = {}
  next_works = {}
  for source, citers in works[d - 1].items():
    for citer in citers['search-results']['entry']:
      if 'fail' in citer:
        print('Skipping citers for source that failed lookup', file = sys.stderr)
        continue
      title = citer['dc:title']
      eid   = citer['eid']
      if eid in next_works:
        if args.verbose: print(f'Not repeating existing {i_engine.ordinal(d + 1)}-level entry for {eid} ("{title}")', file = sys.stderr)
        if eid in next_repeats: next_repeats[eid]['count'] += 1
        else:                   next_repeats[eid] = { 'title': title, 'count': 1 }
        continue
      if args.verbose: print(f'{d:#2}: {title}')
      next_works[eid] = get_citations(title, eid)
  works.append(next_works)
  repeats.append(next_repeats)

exploded = {
  'source': [],
  'target': [],
  'type': 'Undirected',
  'weight': 1,
}

results = []
for d in range(0, args.depth - 1):
  d_ordinal = i_engine.ordinal(d + 1)
  if args.verbose: print(f'{d_ordinal}-level citers')
  count = 0
  bad_count = 0
  for source, citers in works[d].items():
    for citer in citers['search-results']['entry']:
      if 'dc:title' in citer:
        if args.verbose: print('  ' + citer['dc:title'])
        exploded['source'].append(source)
        #exploded['target'].append(citer['dc:title'])
        exploded['target'].append(citer['eid'])
        count += 1
      else:
        if args.verbose: print('  DOH')
        bad_count += 1
  print(f'Found {count + bad_count} {d_ordinal}-level citers')
  if bad_count != 0:
    print(f'Of which, {bad_count} bad cases')
  results.append({'good': count, 'bad': bad_count})

for d, r in enumerate(repeats):
  if len(r) == 0: continue
  print(f'{len(r)} {i_engine.ordinal(d + 1)}-level repeats')
  if args.verbose:
    output = []
    for k, v in r.items():
      output.append(f'  "{v["title"]}" ({k}): {v["count"]} time(s)')
    for n, o in enumerate(sorted(output)):
      print(f'{n + 1:#2}: {o}')

good_total = 0; bad_total = 0
for d, r in enumerate(results):
  good_total += r['good']
  bad_total  += r['bad']
  if args.verbose:
    print(f'{r["good"]}/{r["good"] + r["bad"]} good {i_engine.ordinal(d + 1)}-level results')
print(f'{good_total}/{good_total + bad_total} good total results')


#https://towardsdatascience.com/visualizing-networks-in-python-d70f4cbeb259
edges = pd.DataFrame.from_dict(exploded)
G = nx.from_pandas_edgelist(edges)
#TODO: https://networkx.org/documentation/stable/reference/generated/networkx.classes.function.set_node_attributes.html

net = pyvis.network.Network(notebook = True, cdn_resources = 'remote')
net.from_nx(G)
print('Wrote graph to ', end = '')
net.show('network.html')
