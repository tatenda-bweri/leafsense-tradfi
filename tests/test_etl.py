"""Unit tests for ETL process components"""

import unittest
import os
import json
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase
from pytz import timezone

# Set up Django test environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from app.etl.fetch import fetch_spx_options_data, fetch_market_data
from app.etl.process import process_options_data, format_options_data, calculate_gamma_exposure, filter_options_by_range
from app.etl.load import transform_options_data, load_market_metrics, load_options_data
from app.etl.run import extract_data, etl_process, run_etl

class MockResponse:
    """Mock response object for requests testing"""
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code
        self.text = json.dumps(json_data)
        
    def json(self):
        return self.json_data
        
    def raise_for_status(self):
        if self.status_code != 200:
            raise Exception(f"HTTP Error: {self.status_code}")


class TestFetch(unittest.TestCase):
    """Test cases for data fetching functions"""
    
    @patch('app.etl.fetch.requests.get')
    def test_fetch_spx_options_data_successful(self, mock_get):
        """Test successful API fetch"""
        # Create mock data
        mock_data = {
            'data': {
                'timestamp': '2023-05-01T15:00:00Z',
                'option': {
                    'underlying': '_SPX',
                    'close': '4200.0',
                    'prevClose': '4180.0'
                },
                'options': [
                    {"strikes": [{"strike": "4000", "expiry": "2023-05-19"}]}
                ]
            }
        }
        
        # Set up mock response
        mock_get.return_value = MockResponse(mock_data)
        
        # Import settings to use the actual configured URL
        from django.conf import settings
        symbol = getattr(settings, 'API_DEFAULT_SYMBOL', '_SPX')
        base_url = getattr(settings, 'API_BASE_URL', 'https://cdn.cboe.com/api/global/delayed_quotes/options/')
        expected_url = f"{base_url}{symbol}"
        
        # Call the function - don't provide URL so it uses the configured one
        result = fetch_spx_options_data()
    
        # Assertions
        self.assertEqual(result, mock_data)
        mock_get.assert_called_once()
        # Verify the correct URL was used
        self.assertEqual(mock_get.call_args[0][0], expected_url)
    
    @patch('app.etl.fetch.requests.get')
    def test_fetch_spx_options_data_retry_logic(self, mock_get):
        """Test retry logic on failure"""
        # Set up mock to fail twice then succeed
        mock_get.side_effect = [
            Exception("Connection error"),
            Exception("Timeout"),
            MockResponse({'data': {'success': True}})
        ]
        
        # Call the function without specifying URL to use the configured one
        result = fetch_spx_options_data()
        
        # Assertions
        self.assertEqual(result, {'data': {'success': True}})
        self.assertEqual(mock_get.call_count, 3)
        
        # Import settings to verify the URL used
        from django.conf import settings
        symbol = getattr(settings, 'API_DEFAULT_SYMBOL', '_SPX')
        base_url = getattr(settings, 'API_BASE_URL', 'https://cdn.cboe.com/api/global/delayed_quotes/options/')
        expected_url = f"{base_url}{symbol}"
        
        # Verify all calls used the correct URL
        for call in mock_get.call_args_list:
            self.assertEqual(call[0][0], expected_url)
    
    @patch('app.etl.fetch.fetch_spx_options_data')
    def test_fetch_market_data(self, mock_fetch_options):
        """Test market data extraction"""
        # Create mock options data
        mock_options_response = {
            'data': {
                'option': {
                    'underlying': '_SPX',
                    'close': '4200.0',
                    'prevClose': '4180.0'
                }
            }
        }
        
        # Set up mock
        mock_fetch_options.return_value = mock_options_response
        
        # Call the function
        result = fetch_market_data()
        
        # Assertions
        self.assertEqual(result['symbol'], '_SPX')
        self.assertEqual(result['spot_price'], 4200.0)
        self.assertEqual(result['prev_day_close'], 4180.0)
        self.assertEqual(result['price_change'], 20.0)
        self.assertAlmostEqual(result['price_change_pct'], 0.478, places=3)


class TestProcess(unittest.TestCase):
    """Test cases for data processing functions"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_data = {
            'data': {
                'timestamp': '2023-05-01T15:00:00Z',
                'option': {
                    'underlying': '_SPX',
                    'close': '4200.0',
                    'prevClose': '4180.0'
                },
                'options': [
                    {
                        "strikes": [
                            {
                                "strike": "4000",
                                "expiry": "2023-05-19",
                                "call": {
                                    "option_root": "SPXW",
                                    "option_ext": "230519C4000",
                                    "iv": "0.2",
                                    "delta": "0.6",
                                    "gamma": "0.05",
                                    "open_interest": "1000",
                                    "volume": "500"
                                },
                                "put": {
                                    "option_root": "SPXW",
                                    "option_ext": "230519P4000",
                                    "iv": "0.25",
                                    "delta": "-0.4",
                                    "gamma": "0.04",
                                    "open_interest": "800",
                                    "volume": "400"
                                }
                            },
                            {
                                "strike": "4200",
                                "expiry": "2023-05-19",
                                "call": {
                                    "option_root": "SPXW",
                                    "option_ext": "230519C4200",
                                    "iv": "0.18",
                                    "delta": "0.5",
                                    "gamma": "0.06",
                                    "open_interest": "1200",
                                    "volume": "600"
                                },
                                "put": {
                                    "option_root": "SPXW",
                                    "option_ext": "230519P4200",
                                    "iv": "0.22",
                                    "delta": "-0.5",
                                    "gamma": "0.06",
                                    "open_interest": "900",
                                    "volume": "450"
                                }
                            }
                        ]
                    }
                ]
            }
        }
        
        # Set future expiry date to avoid filtering out during processing
        future_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        for option in self.test_data['data']['options']:
            for strike in option['strikes']:
                strike['expiry'] = future_date
    
    def test_format_options_data(self):
        """Test formatting of options data into DataFrame"""
        tz = timezone("America/New_York")
        today = datetime.now(tz)
        
        # Call the function
        result = format_options_data(self.test_data['data']['options'], today, tz)
        
        # Assertions
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 2)  # Two strikes
        self.assertIn('call_option_symbol', result.columns)
        self.assertIn('put_option_symbol', result.columns)
        self.assertIn('strike_price', result.columns)
        self.assertIn('expiration_date', result.columns)
    
    def test_calculate_gamma_exposure(self):
        """Test gamma exposure calculations"""
        # Create test dataframe
        df = pd.DataFrame({
            'strike_price': [4000, 4200],
            'call_gamma': [0.05, 0.06],
            'put_gamma': [0.04, 0.06],
            'call_open_interest': [1000, 1200],
            'put_open_interest': [800, 900],
        })
        
        spot_price = 4200.0
        
        # Call the function
        result = calculate_gamma_exposure(df, spot_price)
        
        # Assertions
        self.assertIn('call_gamma_exposure', result.columns)
        self.assertIn('put_gamma_exposure', result.columns)
        self.assertIn('total_gamma_exposure', result.columns)
        
        # Check calculation correctness
        # Call gamma exposure = gamma * open_interest * contract_multiplier * (spot_price^2 / 100)
        expected_call_gamma = 0.05 * 1000 * 100 * (4200**2 / 100)
        self.assertAlmostEqual(result['call_gamma_exposure'].iloc[0], expected_call_gamma)
        
        # Put gamma exposure = -1 * gamma * open_interest * contract_multiplier * (spot_price^2 / 100)
        expected_put_gamma = -1 * 0.04 * 800 * 100 * (4200**2 / 100)
        self.assertAlmostEqual(result['put_gamma_exposure'].iloc[0], expected_put_gamma)
    
    def test_filter_options_by_range(self):
        """Test filtering of options by strike price range"""
        # Create test dataframe
        df = pd.DataFrame({
            'strike_price': [3800, 4000, 4200, 4400, 4600],
        })
        
        spot_price = 4200.0
        range_percent = 0.05  # ±5%
        
        # Call the function
        result = filter_options_by_range(df, spot_price, range_percent)
        
        # Assertions
        self.assertEqual(len(result), 3)  # Only strikes within 5% range
        self.assertTrue((result['strike_price'] >= 3990).all())  # Lower bound
        self.assertTrue((result['strike_price'] <= 4410).all())  # Upper bound


class TestLoad(unittest.TestCase):
    """Test cases for data loading functions"""
    
    def test_transform_options_data(self):
        """Test transformation of processed data for database"""
        # Create test dataframe
        now = datetime.now()
        test_df = pd.DataFrame({
            'expiration_date': [now + timedelta(days=30), now + timedelta(days=30)],
            'strike_price': [4000, 4200],
            'time_till_exp': [0.082, 0.082],
            'call_option_symbol': ['SPXW230519C4000', 'SPXW230519C4200'],
            'call_iv': [0.2, 0.18],
            'call_delta': [0.6, 0.5],
            'call_gamma': [0.05, 0.06],
            'call_open_interest': [1000, 1200],
            'call_volume': [500, 600],
            'call_gamma_exposure': [1000000, 1200000],
            'put_option_symbol': ['SPXW230519P4000', 'SPXW230519P4200'],
            'put_iv': [0.25, 0.22],
            'put_delta': [-0.4, -0.5],
            'put_gamma': [0.04, 0.06],
            'put_open_interest': [800, 900],
            'put_volume': [400, 450],
            'put_gamma_exposure': [-800000, -900000],
        })
        
        timestamp = datetime.now()
        
        # Call the function
        result = transform_options_data(test_df, timestamp)
        
        # Assertions
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 4)  # 2 calls and 2 puts
        
        # Check first call record
        call_record = [r for r in result if r['option_type'] == 'CALL' and r['strike_price'] == 4000][0]
        self.assertEqual(call_record['timestamp'], timestamp)
        self.assertEqual(call_record['symbol'], '_SPX')
        self.assertEqual(call_record['option_symbol'], 'SPXW230519C4000')
        self.assertEqual(call_record['iv'], 0.2)
        self.assertEqual(call_record['gamma'], 0.05)
        self.assertEqual(call_record['gamma_exposure'], 1000000)


class TestETLProcess(TestCase):
    """Integration tests for ETL process"""
    
    @patch('app.etl.run.fetch_spx_options_data')
    @patch('app.etl.run.fetch_market_data')
    def test_extract_data(self, mock_fetch_market, mock_fetch_options):
        """Test the data extraction process"""
        # Set up mocks
        future_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        mock_options_data = {
            'data': {
                'timestamp': '2023-05-01T15:00:00Z',
                'option': {
                    'underlying': '_SPX',
                    'close': '4200.0',
                    'prevClose': '4180.0'
                },
                'options': [
                    {
                        "strikes": [
                            {
                                "strike": "4000",
                                "expiry": future_date,
                                "call": {
                                    "option_root": "SPXW",
                                    "option_ext": "230519C4000",
                                    "iv": "0.2",
                                    "delta": "0.6",
                                    "gamma": "0.05",
                                    "open_interest": "1000",
                                    "volume": "500"
                                },
                                "put": {
                                    "option_root": "SPXW",
                                    "option_ext": "230519P4000",
                                    "iv": "0.25",
                                    "delta": "-0.4",
                                    "gamma": "0.04",
                                    "open_interest": "800",
                                    "volume": "400"
                                }
                            }
                        ]
                    }
                ]
            }
        }
        
        mock_market_data = {
            'symbol': '_SPX',
            'spot_price': 4200.0,
            'prev_day_close': 4180.0,
            'price_change': 20.0,
            'price_change_pct': 0.478
        }
        
        mock_fetch_options.return_value = mock_options_data
        mock_fetch_market.return_value = mock_market_data
        
        # Call the function
        filtered_data, market_data, timestamp = extract_data()
        
        # Assertions
        self.assertIsNotNone(filtered_data)
        self.assertFalse(filtered_data.empty)
        self.assertEqual(market_data['spot_price'], 4200.0)
        self.assertIsNotNone(timestamp)
    
    @patch('app.etl.run.extract_data')
    @patch('app.etl.run.transform_options_data')
    @patch('app.etl.run.load_market_metrics')
    @patch('app.etl.run.load_options_data')
    def test_etl_process(self, mock_load_options, mock_load_metrics, mock_transform, mock_extract):
        """Test the full ETL process"""
        # Set up mocks
        mock_extract.return_value = (
            pd.DataFrame({'strike_price': [4000, 4200]}),  # filtered_data
            {'symbol': '_SPX', 'spot_price': 4200.0},  # market_data
            datetime.now()  # timestamp
        )
        
        mock_transform.return_value = [{'option_symbol': 'SPXW230519C4000'}]
        mock_load_metrics.return_value = True
        mock_load_options.return_value = True
        
        # Call the function
        result = etl_process()
        
        # Assertions
        self.assertTrue(result)
        mock_extract.assert_called_once()
        mock_transform.assert_called_once()
        mock_load_metrics.assert_called_once()
        mock_load_options.assert_called_once()
    
    @patch('app.etl.run.etl_process')
    def test_run_etl_success(self, mock_etl_process):
        """Test run_etl wrapper with successful ETL process"""
        # Set up mock
        mock_etl_process.return_value = True
        
        # Call the function
        result = run_etl()
        
        # Assertions
        self.assertTrue(result)
        mock_etl_process.assert_called_once()
    
    @patch('app.etl.run.etl_process')
    def test_run_etl_handles_exceptions(self, mock_etl_process):
        """Test run_etl wrapper handles exceptions properly"""
        # Set up mock to raise an exception
        mock_etl_process.side_effect = Exception("Test error")
        
        # Call the function
        result = run_etl()
        
        # Assertions
        self.assertFalse(result)
        mock_etl_process.assert_called_once()


if __name__ == '__main__':
    unittest.main()