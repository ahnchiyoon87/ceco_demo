import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error

spec = importlib.util.spec_from_file_location('portal_controls', Path(__file__).with_name('server.py'))
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
server.TOKEN = '0' * 64


class PortalControls(unittest.TestCase):
    def test_operator_session_strips_password_and_uses_configured_gate(self):
        user = {'username': 'operator', 'groups': 2, 'token': 'test-session', 'info': '{}',
                'password': 'stored-hash', 'internal': 'private'}
        with patch.multiple(server, FUXA='http://gate:1882', GATE_USER='gate-user', GATE_PASSWORD='gate-secret', OPERATOR_PASSWORD='operator-secret'), patch.object(server.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps({'data': user}).encode())) as call:
            result = server.operator_session()
            self.assertEqual(result['user']['groups'], 2)
            self.assertEqual(result['user']['token'], 'test-session')
            self.assertNotIn('password', result['user'])
            self.assertNotIn('internal', result['user'])
            request = call.call_args.args[0]
            self.assertEqual(request.full_url, 'http://gate:1882/api/signin')
            self.assertEqual(json.loads(request.data), {'username': 'operator', 'password': 'operator-secret'})
            self.assertTrue(request.get_header('Authorization').startswith('Basic '))

    def test_admin_or_invalid_session_is_never_forwarded(self):
        for user in [{'username': 'admin', 'groups': -1, 'token': 'admin-token'},
                     {'username': 'operator', 'groups': 2},
                     {'username': 'operator', 'groups': -1, 'token': 'admin-token'}]:
            with self.subTest(user=user), patch.multiple(server, FUXA='http://gate:1882', GATE_USER='gate-user', GATE_PASSWORD='secret', OPERATOR_PASSWORD='secret'), patch.object(server.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps({'data': user}).encode())):
                with self.assertRaises(server.ControlError) as error:
                    server.operator_session()
                self.assertEqual(error.exception.status, 503)
                self.assertNotIn('token', error.exception.message)

    def test_signin_timeout_never_echoes_secrets_or_retries(self):
        with patch.multiple(server, FUXA='http://gate:1882', GATE_USER='gate-user', GATE_PASSWORD='secret', OPERATOR_PASSWORD='secret'), patch.object(server.urllib.request, 'urlopen', side_effect=urllib.error.URLError('secret-sensitive')) as call:
            with self.assertRaises(server.ControlError) as error:
                server.operator_session()
            call.assert_called_once()
            self.assertNotIn('secret', error.exception.message)

    def test_unknown_fault_and_extra_fields_cannot_reach_the_plant(self):
        for body in [{'scenario': 'unknown'}, {'scenario': 'strainer_fouling', 'duration_s': 0}, {'scenario': []}]:
            with self.subTest(body=body), patch.object(server, 'upstream') as call:
                with self.assertRaises(server.ControlError) as error:
                    server.mutate('/fault', body)
                self.assertEqual(error.exception.status, 400)
                call.assert_not_called()

    def test_neither_new_fault_nor_reset_can_interrupt_approved_work(self):
        for path, body in [('/fault', {'scenario': 'strainer_fouling'}), ('/reset', {})]:
            with self.subTest(path=path), patch.object(server, 'execution_active', return_value=True), patch.object(server, 'upstream') as call:
                with self.assertRaises(server.ControlError) as error:
                    server.mutate(path, body)
                self.assertEqual(error.exception.status, 409)
                call.assert_not_called()

    def test_an_existing_fault_is_not_overwritten(self):
        with patch.object(server, 'execution_active', return_value=False), patch.object(server, 'upstream', return_value={'active_faults': {'bearing_wear': {}}}) as call:
            with self.assertRaises(server.ControlError) as error:
                server.mutate('/fault', {'scenario': 'strainer_fouling'})
            self.assertEqual(error.exception.status, 409)
            call.assert_called_once_with('/state')

    def test_only_one_mutation_is_sent_and_no_ground_truth_or_credential_is_returned(self):
        with patch.object(server, 'execution_active', return_value=False), patch.object(server, 'upstream', side_effect=[{'active_faults': {}}, {'injected': 'strainer_fouling', 'targets': ['secret_internal']}]) as call:
            self.assertEqual(server.mutate('/fault', {'scenario': 'strainer_fouling'}), {'started': 'strainer_fouling'})
            self.assertEqual(call.call_count, 2)
            self.assertEqual(call.call_args.args, ('/fault', {'scenario': 'strainer_fouling'}))

    def test_timeout_does_not_retry_write_or_echo_credentials(self):
        with patch.object(server, 'SIMULATOR', 'http://localhost:1'), patch.object(server, 'USER', 'test-user'), patch.object(server, 'PASSWORD', 'test-secret'), patch.object(server.urllib.request, 'urlopen', side_effect=urllib.error.URLError('secret-sensitive')) as call:
            with self.assertRaises(server.ControlError) as error:
                server.upstream('/fault', {'scenario': 'strainer_fouling'})
            call.assert_called_once()
            self.assertNotIn('secret', error.exception.message)

    def test_cross_origin_and_missing_human_header_are_refused(self):
        handler = object.__new__(server.Handler)
        handler.command = 'POST'
        for headers in [{}, {'X-CECO-Portal': 'interactive', 'X-Portal-Same-Origin': '0'}]:
            handler.headers = headers
            with self.assertRaises(server.ControlError) as error:
                handler.allowed()
            self.assertEqual(error.exception.status, 403)
        handler.headers = {'X-CECO-Portal': 'interactive', 'X-Portal-Same-Origin': '1'}
        with self.assertRaises(server.ControlError):
            handler.allowed()  # Knowledge/AI services have no private portal token.
        handler.headers['X-Portal-Token'] = server.TOKEN
        self.assertIsNone(handler.allowed())


if __name__ == '__main__':
    unittest.main()
