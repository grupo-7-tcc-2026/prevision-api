import base64
import io
import unittest

from fastapi import HTTPException
from PIL import Image

from accounts import ReportRequest, create_report, hash_password, verify_password


class AccountsTests(unittest.TestCase):
    def test_password_hash_uses_unique_salts_and_verifies_password(self):
        first = hash_password("senha de exemplo")
        second = hash_password("senha de exemplo")
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password("senha de exemplo", first))
        self.assertFalse(verify_password("senha incorreta", first))

    def test_report_rejects_malformed_image(self):
        report = ReportRequest(region="Centro", address="Rua Exemplo", image="invalid")
        with self.assertRaises(HTTPException) as error:
            create_report(report, user={"id": 1})
        self.assertEqual(error.exception.status_code, 422)

    def test_report_rejects_unsupported_image(self):
        image = io.BytesIO()
        Image.new("RGB", (2, 2)).save(image, format="BMP")
        report = ReportRequest(
            region="Centro",
            address="Rua Exemplo",
            image=base64.b64encode(image.getvalue()).decode(),
        )
        with self.assertRaises(HTTPException) as error:
            create_report(report, user={"id": 1})
        self.assertEqual(error.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
