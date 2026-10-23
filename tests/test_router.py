import unittest
from unittest.mock import patch
from app.model import Model, ModelError
from app.router import JevRouter, ROUTES


def decision(route):
    return {'model': 'typesafe/jev-test', 'answers': {'route': {
        'type': 'choice', 'choice': route,
        'probabilities': {key: float(key == route) for key in ROUTES}}}}


class RouterTests(unittest.TestCase):
    def test_qwen_required_tools_disable_thinking(self):
        with patch.dict('os.environ', {'CHAT_MODEL': 'qwen/qwen3.7-plus'}):
            client = Model()
            with patch.object(client, 'post', return_value={
                    'choices': [{'message': {'content': 'ok'}}]}) as post:
                client.chat([], [{'type': 'function'}], tool_choice='required')
                self.assertEqual(post.call_args.args[1]['reasoning'], {'enabled': False})
                client.chat([], [{'type': 'function'}])
                self.assertNotIn('reasoning', post.call_args.args[1])

    def test_routes_and_endpoint(self):
        with patch.dict('os.environ', {'ROUTER_MODEL': 'typesafe/jev-1.14'}):
            for route in ROUTES:
                client = Model()
                with patch.object(client, 'post', return_value=decision(route)) as post:
                    result = JevRouter(client).select([{'role': 'user', 'content': 'test'}])
                    self.assertEqual(result['route'], route)
                    args, kwargs = post.call_args
                    self.assertEqual(args[0], '/decisions')
                    self.assertEqual(args[1]['model'], 'typesafe/jev-1.14')
                    self.assertEqual(kwargs['base_url'], 'https://openrouter.ai/api/alpha')

    def test_malformed_answers(self):
        invalid = [{}, {'answers': {'route': {}}}, decision('invalid')]
        for probability in [float('nan'), float('inf'), -1, 2, True]:
            data = decision('database')
            data['answers']['route']['probabilities']['database'] = probability
            invalid.append(data)
        for data in invalid:
            with self.subTest(data=data):
                client = Model()
                with patch.object(client, 'post', return_value=data):
                    with self.assertRaises(ModelError):
                        JevRouter(client).select([])

    def test_provider_failure_is_not_silently_rerouted(self):
        client = Model()
        with patch.object(client, 'post', side_effect=ModelError('provider unavailable')):
            with self.assertRaisesRegex(ModelError, 'unavailable'):
                JevRouter(client).select([])

    def test_chat_preserves_separate_model_and_required_tools(self):
        with patch.dict('os.environ', {'CHAT_MODEL': 'sql-and-generation-model',
                                      'ROUTER_MODEL': 'typesafe/jev-1.14'}):
            client = Model()
            with patch.object(client, 'post', return_value={
                'choices': [{'message': {'content': 'ok'}}]}) as post:
                client.chat([], [{'type': 'function'}], tool_choice='required')
                payload = post.call_args.args[1]
                self.assertEqual(payload['model'], 'sql-and-generation-model')
                self.assertEqual(payload['tool_choice'], 'required')
                self.assertIn('max_tokens', payload)


if __name__ == '__main__':
    unittest.main()
