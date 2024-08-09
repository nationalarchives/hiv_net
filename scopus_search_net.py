#!/usr/bin/env python3
#TODO: Really needs some factoring out to functions to keep the scope under control
#      Particularly due to the ad-hoc instrumentation that I have thrown in here
#TODO: My last note read "reporting should now be wrong but easy to fix"
#      So presumably I had left myself an error that I thought would be obvious as the starting point for the next round of work
#      But a couple of weeks later I find that I have no idea where I am.
#Sample incantation: ./scopus_search_net.py -k keyfile 'AIDS : monitoring response to the public education campaign
#Where keyfile contains an API key

import os
import sys
import json
import pyvis
import inflect
import argparse
import requests
import pandas as pd
import networkx as nx
from collections import defaultdict

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

bad_lookup = 0
errors = defaultdict(int)
repeats = [{}]
for d in range(1, args.depth):
  print(f'Looking up citation level {d}')
  next_repeats = {}
  next_works = {}
  for source, citers in works[d - 1].items():
    if 'fail' in citers:
      print('Skipping citers for source that failed lookup', file = sys.stderr)
      bad_lookup += 1
      continue
    for citer in citers['search-results']['entry']:
      if 'error' in citer:
        errors[citer['error']] += 1
        print(f'Skipping citers due to error "{citer["error"]}"', file = sys.stderr)
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
  try:
    for source, citers in works[d].items():
      if 'search-results' in citer:
        for citer in citers['search-results']['entry']:
          if 'dc:title' in citer:
            if args.verbose: print('  ' + citer['dc:title'])
            exploded['source'].append(source)
            #exploded['target'].append(citer['dc:title'])
            exploded['target'].append(citer['eid'])
            count += 1
          else:
            print(f'  No "dc:title" in citer["search-results"]["entry"] within source {source}. citer is:\n{citer}', file = sys.stderr)
            bad_count += 1
      elif 'fail' in citer:
        print(f'  No "search-results" in citer, but found "fail". Implies lookup error. citer is:\n{citer}', file = sys.stderr)
        bad_count += 1
      else:
        print(f'  Some problem in citer loop', file = sys.stderr)
        bad_count += 1
    print(f'Found {count + bad_count} {d_ordinal}-level citers')
    if bad_count != 0:
      print(f'Of which, {bad_count} bad cases')
    results.append({'good': count, 'bad': bad_count})
  except Exception as e:
    print(f'{d=}\n{d_ordinal=}\n{source=}\n{citers=}\n{citer=}', file = sys.stderr)
    raise e

#values for each member of works list
total_lookup = 0
for level in works:
  total_lookup += len(level)
  bad_lookup   += len([x for x in level.values() if 'fail' in x])
print(f'{total_lookup - bad_lookup}/{total_lookup} good lookups')

for k, v in errors.items():
  print(f'Skipped lookups due to {k}: {v}')

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


#TODO If time, draw a tree where the row is based on publciation year
#     So some rows are empty
#     But we can see the paper ripple through time
#Tree? -- re https://stackoverflow.com/a/57512902
#import matplotlib.pyplot as plt
#import pydot
#from networkx.drawing.nx_pydot import graphviz_layout
#
#T = nx.balanced_tree(2, 5)
#
#nx.draw(G, graphviz_layout(T, prog="dot"))
#net.from_nx(G)
#net.show('tree.html')
