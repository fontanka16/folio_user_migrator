import os
import usaddress
import itertools
import csv
import json
import argparse
from mappers.Aleph import Aleph
from mappers.Alabama import Alabama
from mappers.AlabamaBanner import AlabamaBanner
from mappers.Chalmers import Chalmers


def get_mapper(mapperName, config):
    return {
        'alabama': Alabama(config),
        'alabama_banner': AlabamaBanner(config),
        'aleph': Aleph(config),
        'chalmers': Chalmers(config)
    }[mapperName]


def chunks(myList, size):
     iterator = iter(myList)
     for first in iterator:
         yield itertools.chain([first], itertools.islice(iterator, size - 1))


def map_user_group(groups_map, user):
    folio_group = next((g['Folio Code'] for g
                 in groups_map
                 if g['ILS code'] == user['patronGroup']), 'unmapped')
    if folio_group == 'unmapped':
        raise ValueError("source patron group error: {} for {}"
                         .format(user['patronGroup'], user['id']))
    return folio_group

parser = argparse.ArgumentParser()
parser.add_argument("source_path",
                    help="path of the source file. JSON...")
parser.add_argument("result_path",
                    help="path and name of the results file")
parser.add_argument("groups_map_path",
                    help="path of the group mapping file")
parser.add_argument("mapper",
                    help="which mapper to use")
parser.add_argument("source_name",
                    help="source name")
args = parser.parse_args()

with open(args.groups_map_path, 'r') as groups_map_file:
    groups_map = list(csv.DictReader(groups_map_file))
    config = {"groupsmap": groups_map}
    mapper = get_mapper(args.mapper, config)
    import_struct = {"source_type": args.source_name,
                     "deactivateMissingUsers": False,
                     "users": [],
                     "updateOnlyPresentFields": False,
                     "totalRecords": 0}
    with open(args.source_path, 'r') as source_file:
        file_name = os.path.basename(source_file.name).replace('.json','')
        total_users = 0
        i = 0
        failed_users = 0
        last_counter = dict()
        users_json = mapper.get_users(source_file)
        cs = chunks(users_json, 100)
        for chunk in cs:
            i += 1
            import_struct["users"] = []
            for user_json in chunk:
                try:
                    total_users += 1
                    user = mapper.do_map(user_json[0])
                    patron_group = map_user_group(groups_map, user)
                    # patron group is mapped and set
                    if patron_group != '':
                        user['patronGroup'] = patron_group
                        import_struct["users"].append(user)
                    last_counter = user_json[1]
                    import_struct["totalRecords"] = len(import_struct["users"])
                except ValueError as ee:
                    failed_users += 1
                    print(str(ee))
                except usaddress.RepeatedLabelError as rle:
                    failed_users += 1
                    print("Failed parsing address for user")
                    print(user_json)
                    print(str(rle))
            path = "{}{}_{}_{}.json".format(args.result_path,
                                           args.source_name,
                                           file_name,
                                           str(i))
            with open(path, 'w+') as results_file:
                results_file.write(json.dumps(import_struct, indent=4))
        print("Number of failed users:\t{} out of {} in total"
              .format(failed_users, total_users))
        print(last_counter)
