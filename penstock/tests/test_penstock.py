# -*- coding: utf-8 -*-
import unittest
import munch
import mock
from couchdb import Server, ResourceNotFound

from penstock import run_checker, get_sources_list
from penstock.tests.utils import AlmostAlwaysTrue, get_doc_by_data


class InternalTest(unittest.TestCase):

    def setUp(self):
        self.test_data = {
            'target': 'http://target_of_replication',
            'source': 'source_of_replication'
        }
        self.configuration = {
            'admin': 'http://localhost:5984',
            'target': self.test_data['target'],
            'sources': [
                {'url': self.test_data['source']}
            ]
        }
        self.server = Server(self.configuration['admin'])
        try:
            test_db = self.server['test_replication']
            del test_db
            self.server.delete('test_replication')
            test_db = self.server.create('test_replication')
        except ResourceNotFound:
            test_db = self.server.create('test_replication')

        self.patch_server = mock.patch('penstock.Server')
        self.mocked_server = self.patch_server.start()
        self.mocked_server.return_value = munch.Munch(
            {
                '_replicator': test_db,
                'tasks': self.server.tasks
            }
        )

        self.patch_check_replication = mock.patch('penstock.CHECK_REPLICATION',  AlmostAlwaysTrue(1))
        self.patch_check_replication.start()

        self.patch_sleep = mock.patch('penstock.sleep')
        self.patch_sleep.start()

    def tearDown(self):
        self.patch_server.stop()
        self.patch_sleep.stop()
        self.patch_check_replication.stop()
        del self.server['test_replication']

    def test_replication_from_source(self):
        run_checker(self.configuration)
        db = self.server['test_replication']

        replica_doc = get_doc_by_data(db, self.test_data)

        self.assertIsNotNone(replica_doc)
        self.assertEqual(replica_doc['source'], self.test_data['source'])
        self.assertEqual(replica_doc['target'], self.test_data['target'])

    def test_delete_replication(self):
        # Call run checker to create replication
        with mock.patch('penstock.CHECK_REPLICATION',  AlmostAlwaysTrue(1)):
            run_checker(self.configuration)
        db = self.server['test_replication']

        replica_doc = get_doc_by_data(db, self.test_data)

        self.assertIsNotNone(replica_doc)
        self.assertEqual(replica_doc['source'], self.test_data['source'])
        self.assertEqual(replica_doc['target'], self.test_data['target'])

        # Call run checker to delete replication that is not triggered
        replica_doc['_replication_state'] = 'not_triggered'
        db.save(replica_doc)

        with mock.patch('penstock.CHECK_REPLICATION',  AlmostAlwaysTrue(1)):
            run_checker(self.configuration)

        replica_doc = get_doc_by_data(db, self.test_data)

        self.assertIsNone(replica_doc)


class GetSourcesListTest(unittest.TestCase):

    def setUp(self):
        self.configuration = {
            'sources': [
                {'url': 'source_of_replication_1'},
                {'url': 'source_of_replication_2'}
            ]
        }

        self.patch_consul = mock.patch('penstock.Consul')
        self.mocked_consul = self.patch_consul.start()
        self.mocked_consul_instance = mock.MagicMock()
        self.mocked_consul.return_value = self.mocked_consul_instance

        self.patch_socket = mock.patch('penstock.socket')
        self.mocked_socket = self.patch_socket.start()

    def tearDown(self):
        self.patch_socket.stop()
        self.patch_consul.stop()

    def test_get_consul_sources(self):
        self.configuration['consul_sources'] = {
            'name': 'consul_source_name'
        }
        self.mocked_consul_instance.catalog.service.return_value = (
            'value',
            [
                {'ServiceID': 'consul_service_id'}
            ]
        )

        sources = get_sources_list(self.configuration)

        self.assertEqual(self.mocked_consul_instance.catalog.service.call_count, 1)
        self.mocked_consul_instance.catalog.service.assert_called_with(
            self.configuration['consul_sources']['name'],
            tag=None
        )

        self.assertEqual(sources, {'consul_service_id'})

    def test_get_simple_sources(self):
        sources = get_sources_list(self.configuration)
        self.assertEqual(sources, {'source_of_replication_1', 'source_of_replication_2'})

    def test_get_dns_sources(self):
        self.configuration['dns_sources'] = {
            'dns_url': 'consul_source_name',
            'user': 'some-user',
            'password': 'password',
            'port': '8090',
            'database': 'db_name'
        }

        returned_socket_addresses = [
            ('', '', '', '', ('address', 80, 0, 0)),
        ]

        self.mocked_socket.getaddrinfo.return_value = returned_socket_addresses

        sources = get_sources_list(self.configuration)

        self.assertEqual(self.mocked_socket.getaddrinfo.call_count, 1)
        self.mocked_socket.getaddrinfo.assert_called_with(
            self.configuration['dns_sources']['dns_url'],
            80
        )

        resulted_url = 'http://{1[user]}:{1[password]}@{0}:{1[port]}/{1[database]}'.format(
            returned_socket_addresses[0][4][0],
            self.configuration['dns_sources']
        )
        self.assertEqual(sources, {resulted_url})


def suite():
    tests = unittest.TestSuite()
    tests.addTest(unittest.makeSuite(InternalTest))
    tests.addTest(unittest.makeSuite(GetSourcesListTest))
    return tests


if __name__ == '__main__':
    unittest.main(defaultTest='suite')