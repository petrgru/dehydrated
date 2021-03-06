#!/usr/bin/env python3
# dnsmadeeasy hook for letsencrypt.sh
# http://www.dnsmadeeasy.com/integration/pdf/API-Docv2.pdf

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from builtins import str

from future import standard_library
standard_library.install_aliases()

import argparse
import subprocess
from suds.client import Client
import datetime
import syslog
import dns.exception
import dns.resolver
import logging
import os
import requests
import sys
import time

from email.utils import formatdate
from datetime import datetime
from time import mktime
import hashlib, hmac

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

# Calculate RFC 1123 HTTP/1.1 date
now = datetime.now()
stamp = mktime(now.timetuple())
requestDate =  formatdate(
    timeval     = stamp,
    localtime   = False,
    usegmt      = True
)

try:
    A24_USER=os.environ['API_USER']
    A24_PASS=os.environ['API_PASS']

except KeyError:
    logger.error(" + Unable to locate dnsmadeeasy credentials in environment!")
    sys.exit(1)

try:
    dns_servers = os.environ['QUERY_DNS_SERVERS']
    dns_servers = dns_servers.split()
except KeyError:
    dns_servers = False

def check_errors(result):
    if len(result.errors) != 0:
        # print(result.errors[0].item[0].value[0])
        syslog.syslog(syslog.LOG_ERR, 'active24Soap failed request: ' + result.errors[0].item[0].value[0])
        exit(1)


def _has_dns_propagated(name, token):
    txt_records = []
    try:
        if dns_servers:
            custom_resolver = dns.resolver.Resolver(configure=False)
            custom_resolver.nameservers = dns_servers
            dns_response = custom_resolver.query(name, 'TXT')
        else:
            dns_response = dns.resolver.query(name, 'TXT')
        for rdata in dns_response:
            for txt_record in rdata.strings:
                txt_records.append(txt_record.decode())
    except dns.exception.DNSException as error:
        return False

    for txt_record in txt_records:
        if txt_record == bytearray(token, 'ascii'):
            return True

    return False

# http://api.dnsmadeeasy.com/V2.0/dns/managed/id/{domainname}
def _get_zone_id(domain):
    # allow both tlds and subdomains hosted on DNSMadeEasy
    tld = domain[domain.find('.')+1:]
    url = DME_API_BASE_URL[DME_SERVER]
    r = requests.get(url, headers=DME_HEADERS)
    r.raise_for_status()
    for record in r.json()['data']:
        if (record['name'] == tld) or ("." + record['name'] in tld):
            return record['id']
    logger.error(" + Unable to locate zone for {0}".format(tld))
    sys.exit(1)

# http://api.dnsmadeeasy.com/V2.0/dns/managed/id/{domainname}
def _get_zone_name(domain):
    # allow both tlds and subdomains hosted on DNSMadeEasy
    tld = domain[domain.find('.')+1:]
    r = client.service.getDnsRecords(tld)
    check_errors(result)
    return domain
    #r.raise_for_status()
    #for record in r['data']:
    #    if (record['name'] == tld) or ("." + record['name'] in tld):
    #        return record['name']
    logger.error(" + Unable to locate zone for {0}".format(tld))
    sys.exit(1)

def _get_txt_record(client, domain, name, record_type='TXT'):
    '''finds DNS recodr by Name and Type'''
    result = client.service.getDnsRecords(domain)
    check_errors(result)
    dnsrecord = None
    for record in result.data:
        if (record.type == record_type) and (record.name == name):
            dnsrecord = record
    if dnsrecord is None:
        # print('DNS Record not found')
        client.service.logout()
        exit(1)
    return dnsrecord

# http://api.dnsmadeeasy.com/V2.0/dns/managed/{domain_id}/records?type=TXT&recordName={name}
def _get_txt_record_id(zone_id, name):
    url = DME_API_BASE_URL[DME_SERVER] + "/{0}/records?type=TXT&recordName={1}".format(zone_id, name)
    r = requests.get(url, headers=DME_HEADERS)
    r.raise_for_status()
    try:
        record_id = r.json()['data'][0]['id']
    except IndexError:
        logger.info(" + Unable to locate record named {0}".format(name))
        return

    return record_id

#def create_record(client, ip, ttl, domain, record_type, name):
def create_txt_record(args):
    domain, token = args[0], args[2]
    # zone_id = _get_zone_id(domain)
    name = "{0}.{1}".format('_acme-challenge', domain)
    short_name = "{0}.{1}".format('_acme-challenge', domain[0:-(len(_get_zone_name(domain)) + 1)])

    '''Creates new DNS record'''
    record_type='TXT'
    newrecord = client.factory.create('DnsRecord' + str(record_type))
    newrecord['from'] = datetime.utcnow()
    newrecord['to'] = datetime.utcfromtimestamp(2147483647)
    ttl = 3600
    newrecord.ttl = ttl
    newrecord.type = client.factory.create('soapenc:string')
    newrecord.type.value = record_type
    newrecord.text = token
    newrecord.name.value = name
    #newrecord.value = client.factory.create('soapenc:Array')
    #newrecord.value.item = [newrecord.ip]
    # print(newrecord)
    result = client.service.addDnsRecord(newrecord, domain)
    check_errors(result)
    # print('New DNS record created.')


# http://api.dnsmadeeasy.com/V2.0/dns/managed/{domain_id}/records
def create1_txt_record(args):
    domain, token = args[0], args[2]
    #zone_id = _get_zone_id(domain)
    name = "{0}.{1}".format('_acme-challenge', domain)
    short_name = "{0}.{1}".format('_acme-challenge', domain[0:-(len(_get_zone_name(domain))+1)])
    url = DME_API_BASE_URL[DME_SERVER] + "/{0}/records".format(zone_id)
    payload = {
        'type': 'TXT',
        'name': short_name,
        'value': token,
        'ttl': 5,
    }
    r = requests.post(url, headers=DME_HEADERS, json=payload)
    r.raise_for_status()
    record_id = r.json()['id']
    logger.debug(" + TXT record created, ID: {0}".format(record_id))

    # give it 10 seconds to settle down and avoid nxdomain caching
    logger.info(" + Settling down for 10s...")
    time.sleep(10)

    retries=2
    while(_has_dns_propagated(name, token) == False and retries > 0):
        logger.info(" + DNS not propagated, waiting 30s...")
        retries-=1
        time.sleep(30)

    if retries <= 0:
        logger.error("Error resolving TXT record in domain {0}".format(domain))
        sys.exit(1)

# http://api.dnsmadeeasy.com/V2.0/dns/managed/{domain_id}/records
def delete_txt_record(args):
    domain, token = args[0], args[2]
    if not domain:
        logger.info(" + http_request() error in letsencrypt.sh?")
        return

    zone_id = _get_zone_id(domain)
    name = "{0}.{1}".format('_acme-challenge', domain)
    short_name = "{0}.{1}".format('_acme-challenge', domain[0:-(len(_get_zone_name(domain))+1)])
    record_id = _get_txt_record_id(zone_id, short_name)

    logger.debug(" + Deleting TXT record name: {0}".format(name))
    url = DME_API_BASE_URL[DME_SERVER] + "/{0}/records/{1}".format(zone_id, record_id)
    r = requests.delete(url, headers=DME_HEADERS)
    r.raise_for_status()


def deploy_cert(args):
    domain, privkey_pem, cert_pem, fullchain_pem, chain_pem, timestamp = args
    logger.info(' + ssl_certificate: {0}'.format(fullchain_pem))
    logger.info(' + ssl_certificate_key: {0}'.format(privkey_pem))
    return

def main(argv):
    hook_name, args = argv[0], argv[1:]

    ops = {
        'deploy_challenge': create_txt_record,
        'clean_challenge' : delete_txt_record,
        'deploy_cert'     : deploy_cert,
    }

    if hook_name in ops.keys():
        logger.info(' + active24 hook executing: %s', hook_name)
        ops[hook_name](args)
    else:
        logger.debug(' + active24 hook not executing: %s', hook_name)


if __name__ == '__main__':
    client = Client(
        'https://centrum.active24.cz/services/a24PartnerService?wsdl')

    # login
    result = client.service.login(A24_USER, A24_PASS)
    check_errors(result)
    main(sys.argv[1:])
