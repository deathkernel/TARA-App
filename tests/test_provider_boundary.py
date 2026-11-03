import unittest
from tara_app.provider_boundary import OptionalProvider, ProviderDisabledError

class ProviderBoundaryTests(unittest.TestCase):
    def test_remote_provider_is_disabled_by_default(self):
        with self.assertRaises(ProviderDisabledError): OptionalProvider(lambda payload: "ok").complete({})

    def test_enabled_provider_uses_injected_transport(self):
        provider = OptionalProvider(lambda payload: payload["input"], enabled=True)
        self.assertEqual(provider.complete({"input": "ok"}), "ok")

    def test_rejects_non_mapping_payload(self):
        provider = OptionalProvider(lambda payload: "ok", enabled=True)
        with self.assertRaises(ValueError): provider.complete([])

if __name__ == "__main__": unittest.main()
