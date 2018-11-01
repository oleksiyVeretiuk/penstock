# -*- coding: utf-8 -*-
"""
Penstock (Coucdb Replication Manager)
"""
from gevent import monkey
monkey.patch_all()

import logging
from logging.config import dictConfig
import argparse
import gevent
from consul import Consul
import socket
from random import sample
from couchdb.client import Database, Server
from yaml import load
from time import sleep
import sys, os
from urlparse import urlparse

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

logger = logging.getLogger('replichecker')


CHECK_REPLICATION = True


def get_tasks_for_replications(server, replicators_documents):
    doc_ids = [replicator_document['_id'] for replicator_document in replicators_documents]
    tasks = []
    for task in server.tasks():
        if task['type'] == 'replication' and task.get('doc_id', None) in doc_ids:
            logger.info(
                "Current progress ({0[replication_id]}): {0[progress]}".format(
                    task), extra={'REPLICATIONS_PROGRESS': task['progress']})
            tasks.append(task)
    return tasks


def create_replication(replicator_db, target, source):
    logger.info("Create replication.")
    replicator_document_id = replicator_db.create({
        'create_target': True,
        'continuous': True,
        'target': target,
        'source': source
    })
    replicator_document = replicator_db.get(replicator_document_id)
    parsed_source = urlparse(replicator_document.get('source', ''))
    if parsed_source.hostname:
        replication_direction = \
            '{0.hostname}{0.path} -> {1.hostname}{1.path}'.format(
                parsed_source,
                urlparse(replicator_document.get('target', '')))
    else:
        replication_direction = \
            '{0.path} -> {1.hostname}{1.path}'.format(
                parsed_source,
                urlparse(replicator_document.get('target', '')))
    logger.info("Replication created ({})".format(replication_direction),
                extra={'MESSAGE_ID': 'CREATE_REPLICATION'})
    return replicator_document


def get_sources_list(configuration):
    if 'consul_sources' in configuration:
        consul_conf = configuration['consul_sources']
        c = Consul()
        services = c.catalog.service(consul_conf['name'], tag=consul_conf.get('tag', None))[1]
        return set([service['ServiceID'] for service in services])
    elif 'dns_sources' in configuration:
        consul_conf = configuration['dns_sources']
        return set(["http://{1[user]}:{1[password]}@{0}:{1[port]}/{1[database]}".format(str(i[4][0]), consul_conf)
                    for i in socket.getaddrinfo(consul_conf['dns_url'], 80)])
    else:
        return set([source['url'] for source in configuration['sources']])


def run_checker(configuration):
    server = Server(configuration['admin'])
    replicator_db = server['_replicator']
    minimal_replications = int(configuration.get('minimal_replications', 1))
    sources_list = get_sources_list(configuration)
    if minimal_replications > len(sources_list):
        logger.error("Replications count is lower then possible sources list",
                     extra={'MESSAGE_ID': 'REPLICATIONS_COUNT_IS_LOWER'})
        return
    black_listed_sources = set([])
    while CHECK_REPLICATION:
        replicator_documents = []
        for i in range(minimal_replications):
            replicator_document = None
            for replication_id in replicator_db:
                if replication_id.startswith('_design/'):
                    continue
                temp_replicator_document = replicator_db.get(replication_id)
                if temp_replicator_document['target'] != configuration['target'] and temp_replicator_document.get('continuous', False):
                    continue
                if temp_replicator_document['source'] not in sources_list:
                    continue
                if temp_replicator_document.get('_replication_state', '') != 'triggered':
                    logger.info("Delete replication. ID: {0[_id]}".format(temp_replicator_document),
                                extra={'MESSAGE_ID': 'DELETE_REPLICATION'})
                    black_listed_sources.add(temp_replicator_document['source'])
                    logger.info('Blacklisted: {}'.format(temp_replicator_document.get('source', '').split('@')[-1]),
                                extra={'MESSAGE_ID': 'BLACKLISTED'})
                    replicator_db.delete(temp_replicator_document)
                    continue
                if temp_replicator_document['source'] in [rep['source'] for rep in replicator_documents]:
                    continue
                replicator_document = temp_replicator_document
                break
            if not replicator_document:
                logger.info("No active replication")
                white_listed_sources = sources_list - black_listed_sources
                white_listed_sources -= set([replication['source'] for replication in replicator_documents])
                if white_listed_sources:
                    replicator_document = create_replication(replicator_db,
                                                             configuration['target'],
                                                             sample(white_listed_sources, 1)[0])
                else:
                    logger.warning("No white listed sources")
                    sleep(30)
                    logger.warning("Start with all listed sources")
                    black_listed_sources = set([])
                    continue
            replicator_documents.append(replicator_document)
        sleep(5)
        while len(get_tasks_for_replications(server, replicator_documents)) == minimal_replications:
            sleep(10)

        logger.info("Wait replication.")
        sleep(10)


def main():
    parser = argparse.ArgumentParser(description='---- Penstock ----')
    parser.add_argument('config', type=str, help='Path to configuration file')
    params = parser.parse_args()
    logger.info("Start Penstock.")
    if os.path.isfile(params.config):
        with open(params.config) as config_file_obj:
            config = load(config_file_obj.read())
        dictConfig(config)
        replications = {}
        for replication_id in config:
            if replication_id.startswith('replication_'):
                logger.info("Start replication {}".format(replication_id))
                replications[replication_id] = gevent.spawn(run_checker, config[replication_id])
        while 1:
            for replication_id in replications:
                if replications[replication_id].ready():
                    sleep(10)
                    logger.info("Handle restart replication {}".format(replication_id))
                    replications[replication_id] = gevent.spawn(run_checker, config[replication_id])
            sleep(30)


##############################################################

if __name__ == "__main__":
    main()
