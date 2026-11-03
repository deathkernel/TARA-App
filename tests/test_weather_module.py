import unittest
from tara_weather.__main__ import _location, handle_request

class WeatherTests(unittest.TestCase):
    def test_adapter_health_does_not_call_network(self):
        result=handle_request({"schema_version":"1.0","request_id":"h","module":"weather","action":"health"})
        self.assertEqual(result["status"],"success"); self.assertTrue(result["data"]["healthy"])
    def test_extract_city(self): self.assertEqual(_location("weather in Pune today"),"Pune")
    def test_extract_city_with_natural_language_and_forecast_range(self): self.assertEqual(_location("What is the weather like in Pune for next 7 days?"),"Pune")
    def test_requires_location(self):
        result=handle_request({"schema_version":"1.0","request_id":"x","module":"weather","action":"forecast","inputs":{"question":"weather please"}})
        self.assertEqual(result["status"],"invalid_request")
    def test_invalid_schema_fails_closed(self):
        result=handle_request({"schema_version":"2.0","request_id":"x","module":"weather","action":"forecast","inputs":{}})
        self.assertEqual(result["status"],"invalid_request")
if __name__=="__main__": unittest.main()
