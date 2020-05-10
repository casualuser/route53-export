import io
import sys
import dns.zone
import json
import boto3

from os import path
from configparser import ConfigParser


def print_to_string(*args, **kwargs):
    output = io.StringIO()
    print(*args, file=output, **kwargs)
    contents = output.getvalue()
    output.close()

    return contents


def get_settings_ini():
    config = ConfigParser()
    config.read('zone.ini')

    return config


def get_settings_json():
    with open('zone.json', 'r') as f:
        config = json.load(f)

    return config


def set_settings():
    if path.exists('zone.json'):
        config = get_settings_json()
    elif path.exists('zone.ini'):
        config = get_settings_ini()

    # os.environ.get('SECRET_KEY', None)
    return config


def client_setup(config):
    if config['aws_access_key_id'] and config['aws_secret_access_key']:
        client = boto3.client(
            'route53',
            aws_access_key_id=config['aws_access_key_id'],
            aws_secret_access_key=config['aws_secret_access_key']
        )
    else:
        client = boto3.client('route53')

    return client


def get_zone_from_file(config):
    path = ''
    if config['zone_file_path']:
        path = config['zone_file_path']
    else:
        path = './'
    
    zone_file = open(path + 'zone.txt')
    zone_block = ""
    found = False
    for line in zone_file:
        if found:
            if line.strip() == "; END ROUTE53 MANAGED BLOCK":
                break
            zone_block += line
        else:
            if line.strip() == "; BEGIN ROUTE53 MANAGED BLOCK":
                found = True

    return zone_block


def get_zone_origin(config):
    client = client_setup(config)

    try:
        zone_id = config['hosted_zone_id']
        zone = client.get_hosted_zone(Id=zone_id)
        origin = zone['HostedZone']['Name']
    except Exception as e:
        print('requested zone doesn\'t exist')
        sys.exit(1)

    return origin


def get_zone_from_route53(config):
    client = client_setup(config)
    zones = ""

    try:
        origin = get_zone_origin(config)
        zone_id = config['hosted_zone_id']
    except Exception as e:
        print('requested zone doesn\'t exist')
        sys.exit(1)

    if origin and zone_id:
        records = client.list_resource_record_sets(HostedZoneId=zone_id)

    if records:
        for record in records['ResourceRecordSets']:
            if record.get('ResourceRecords'):
                for target in record['ResourceRecords']:
                    zone = print_to_string(record['Name'], record['TTL'], 'IN', record['Type'], target['Value'], sep = '\t')
                    zones += zone
            elif record.get('AliasTarget'):
                zone = print_to_string(record['Name'], 300, 'IN', record['Type'], record['AliasTarget']['DNSName'], '; ALIAS', sep = '\t')
                zones += zone
            else:
                raise Exception('Unknown record type: {}'.format(record))

    return zones


def parse_zone(zone, origin):
    parsed_zone = dns.zone.from_text(zone, origin=origin, relativize=False, check_origin=False)
    return parsed_zone


# zone_file_path - File which will be used by script to update
# hosted_zone_id - AWS private zone id
# filter_record_types - which records types to be exported (array - A, TXT, AAAA, CNAME etc)

# ------- main -------
config = set_settings()

origin = get_zone_origin(config)

zone_from_file = get_zone_from_file(config)
print(zone_from_file)
parse_zone(zone_from_file, origin)

print('- ' * 20)

zone_from_route53 = get_zone_from_route53(config)
print(zone_from_route53)
parse_zone(zone_from_route53, origin)