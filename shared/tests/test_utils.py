"""
Tests for shared utility functions
"""

from django.test import TestCase
from django.http import HttpResponse
from shared.utils import (
    format_currency, 
    truncate_text, 
    get_status_color,
    safe_dict_get,
    build_query_string,
    render_turbo_stream
)


class TestFormatCurrency(TestCase):
    
    def test_format_positive_amount(self):
        """Test formatting positive currency amounts"""
        self.assertEqual(format_currency(100.50), "AUD 100.50")
        self.assertEqual(format_currency(1234.56, "USD"), "USD 1,234.56")
    
    def test_format_negative_amount(self):
        """Test formatting negative currency amounts"""
        self.assertEqual(format_currency(-100.50), "-AUD 100.50")
        self.assertEqual(format_currency(-1234.56, "USD"), "-USD 1,234.56")
    
    def test_format_zero_amount(self):
        """Test formatting zero amount"""
        self.assertEqual(format_currency(0), "AUD 0.00")
    
    def test_format_none_amount(self):
        """Test formatting None amount returns dash"""
        self.assertEqual(format_currency(None), "—")


class TestTruncateText(TestCase):
    
    def test_truncate_long_text(self):
        """Test truncating text longer than max_length"""
        text = "This is a very long piece of text that should be truncated"
        result = truncate_text(text, 20)
        self.assertEqual(result, "This is a very lo...")
        self.assertEqual(len(result), 20)
    
    def test_truncate_short_text(self):
        """Test text shorter than max_length is unchanged"""
        text = "Short text"
        result = truncate_text(text, 20)
        self.assertEqual(result, "Short text")
    
    def test_truncate_exact_length(self):
        """Test text exactly at max_length is unchanged"""
        text = "Exactly twenty chars"  # 20 characters
        result = truncate_text(text, 20)
        self.assertEqual(result, "Exactly twenty chars")
    
    def test_truncate_empty_text(self):
        """Test empty text returns empty string"""
        self.assertEqual(truncate_text(""), "")
        self.assertEqual(truncate_text(None), "")


class TestGetStatusColor(TestCase):
    
    def test_known_status_colors(self):
        """Test known status returns correct color"""
        self.assertEqual(get_status_color('active'), 'text-green-600')
        self.assertEqual(get_status_color('error'), 'text-red-600')
        self.assertEqual(get_status_color('pending'), 'text-yellow-600')
    
    def test_case_insensitive_status(self):
        """Test status color is case insensitive"""
        self.assertEqual(get_status_color('ACTIVE'), 'text-green-600')
        self.assertEqual(get_status_color('Active'), 'text-green-600')
    
    def test_unknown_status_default(self):
        """Test unknown status returns default color"""
        self.assertEqual(get_status_color('unknown'), 'text-gray-500')
        self.assertEqual(get_status_color(''), 'text-gray-500')


class TestSafeDictGet(TestCase):
    
    def test_get_existing_key(self):
        """Test getting existing key from dictionary"""
        data = {'name': 'John', 'age': 30}
        self.assertEqual(safe_dict_get(data, 'name'), 'John')
        self.assertEqual(safe_dict_get(data, 'age'), 30)
    
    def test_get_missing_key_with_default(self):
        """Test getting missing key returns default"""
        data = {'name': 'John'}
        self.assertEqual(safe_dict_get(data, 'age', 0), 0)
        self.assertEqual(safe_dict_get(data, 'city', 'Unknown'), 'Unknown')
    
    def test_get_missing_key_no_default(self):
        """Test getting missing key without default returns None"""
        data = {'name': 'John'}
        self.assertIsNone(safe_dict_get(data, 'age'))
    
    def test_non_dict_input(self):
        """Test non-dict input returns default"""
        self.assertEqual(safe_dict_get("not a dict", 'key', 'default'), 'default')
        self.assertEqual(safe_dict_get(None, 'key', 'default'), 'default')
        self.assertIsNone(safe_dict_get([], 'key'))


class TestBuildQueryString(TestCase):
    
    def test_build_simple_query_string(self):
        """Test building simple query string"""
        params = {'page': 1, 'limit': 10}
        result = build_query_string(params)
        self.assertIn('page=1', result)
        self.assertIn('limit=10', result)
        self.assertTrue(result.startswith('?'))
    
    def test_filter_none_values(self):
        """Test None values are filtered out"""
        params = {'page': 1, 'search': None, 'limit': 10}
        result = build_query_string(params)
        self.assertIn('page=1', result)
        self.assertIn('limit=10', result)
        self.assertNotIn('search', result)
    
    def test_empty_params(self):
        """Test empty params returns empty string"""
        self.assertEqual(build_query_string({}), "")
        self.assertEqual(build_query_string(None), "")
    
    def test_all_none_params(self):
        """Test all None params returns empty string"""
        params = {'search': None, 'filter': None}
        self.assertEqual(build_query_string(params), "")


class TestRenderTurboStream(TestCase):
    
    def test_render_turbo_stream_response(self):
        """Test turbo stream response is properly formatted"""
        response = render_turbo_stream(
            action='replace',
            target='#content',
            template='shared/test_partial.html',
            context={'message': 'Hello World'}
        )
        
        # Check response type and content type
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response['Content-Type'], 'text/vnd.turbo-stream.html')
        
        # Check content contains turbo-stream tags
        content = response.content.decode()
        self.assertIn('<turbo-stream action="replace" target="#content">', content)
        self.assertIn('<template>', content)
        self.assertIn('</template>', content)
        self.assertIn('</turbo-stream>', content)
    
    def test_render_turbo_stream_no_context(self):
        """Test turbo stream works without context"""
        response = render_turbo_stream(
            action='remove',
            target='#item-123',
            template='shared/test_partial.html'
        )
        
        self.assertIsInstance(response, HttpResponse)
        content = response.content.decode()
        self.assertIn('<turbo-stream action="remove" target="#item-123">', content)