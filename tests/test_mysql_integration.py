import base64
import io
import os
import unittest
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from accounts import database, router


@unittest.skipUnless(os.environ.get("TEST_MYSQL") == "1", "MySQL integration test not enabled")
class MysqlIntegrationTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.emails = [f"test-{uuid.uuid4().hex}@example.invalid" for _ in range(2)]

    def tearDown(self):
        with database() as connection:
            cursor = connection.cursor()
            try:
                for email in self.emails:
                    cursor.execute("DELETE FROM app_users WHERE email = %s", (email,))
                connection.commit()
            finally:
                cursor.close()
        self.client.close()

    def test_accounts_and_reports_are_isolated(self):
        tokens = []
        for email in self.emails:
            registration = self.client.post("/auth/register", json={
                "name": "Teste", "email": email, "password": "test-password-123"
            })
            self.assertEqual(registration.status_code, 201)
            login = self.client.post("/auth/login", json={"email": email, "password": "test-password-123"})
            self.assertEqual(login.status_code, 200)
            tokens.append(login.json()["token"])

        headers = [{"Authorization": f"Bearer {token}"} for token in tokens]
        image = io.BytesIO()
        Image.new("RGB", (2, 2), "red").save(image, format="PNG")
        report = self.client.post("/reports", headers=headers[0], json={
            "region": "Centro", "address": "Rua de teste",
            "image": base64.b64encode(image.getvalue()).decode(),
        })
        self.assertEqual(report.status_code, 201)
        report_id = report.json()["id"]
        self.assertEqual(len(self.client.get("/reports", headers=headers[0]).json()), 1)
        self.assertEqual(self.client.get("/reports", headers=headers[1]).json(), [])
        self.assertEqual(self.client.get(f"/reports/{report_id}/image", headers=headers[0]).content, image.getvalue())
        self.assertEqual(self.client.get(f"/reports/{report_id}/image", headers=headers[1]).status_code, 404)
        self.assertEqual(self.client.delete(f"/reports/{report_id}", headers=headers[1]).status_code, 404)
        self.assertEqual(self.client.delete(f"/reports/{report_id}", headers=headers[0]).status_code, 204)
        self.assertEqual(self.client.post("/auth/logout", headers=headers[0]).status_code, 204)
        self.assertEqual(self.client.get("/auth/me", headers=headers[0]).status_code, 401)
