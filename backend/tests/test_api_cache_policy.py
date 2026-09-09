import unittest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import create_app


class ApiCachePolicyTests(unittest.TestCase):
    def test_success_and_auth_failures_cannot_be_cached(self):
        app = create_app()
        @app.get('/test-private-data')
        def private():
            return {'fixture': 'private'}
        @app.get('/test-expired-session')
        def expired():
            raise HTTPException(status_code=401, detail='Expired')
        # No lifespan startup or production database access.
        client = TestClient(app)
        for path, expected in [('/test-private-data', 200), ('/test-expired-session', 401)]:
            response = client.get(path, headers={'Origin': 'https://www.skubase.io'})
            self.assertEqual(response.status_code, expected)
            self.assertEqual(response.headers['cache-control'], 'private, no-store')
            self.assertEqual(response.headers['access-control-allow-origin'], 'https://www.skubase.io')
        preflight = client.options('/test-private-data', headers={'Origin': 'https://www.skubase.io', 'Access-Control-Request-Method': 'GET'})
        self.assertEqual(preflight.status_code, 200)
        self.assertEqual(preflight.headers['access-control-max-age'], '7200')
        client.close()
