from django.test.runner import DiscoverRunner
import sys


class ColoredTestRunner(DiscoverRunner):
    """Custom test runner with colored output for better readability."""
    
    def __init__(self, verbosity=1, interactive=True, failfast=False, keepdb=False, reverse=False, debug_mode=False, debug_sql=False, parallel=0, tags=None, exclude_tags=None, test_name_patterns=None, pdb=False, buffer=False, enable_faulthandler=True, timing=False, shuffle=False, **kwargs):
        super().__init__(verbosity=verbosity, interactive=interactive, failfast=failfast, keepdb=keepdb, reverse=reverse, debug_mode=debug_mode, debug_sql=debug_sql, parallel=parallel, tags=tags, exclude_tags=exclude_tags, test_name_patterns=test_name_patterns, pdb=pdb, buffer=buffer, enable_faulthandler=enable_faulthandler, timing=timing, shuffle=shuffle, **kwargs)
    
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        # Suppress the verbose output we don't want
        import logging
        logging.disable(logging.CRITICAL)
    
    def run_tests(self, test_labels, **kwargs):
        # Override verbosity to reduce noise
        old_verbosity = self.verbosity
        self.verbosity = 0
        
        result = super().run_tests(test_labels, **kwargs)
        
        # Restore original verbosity
        self.verbosity = old_verbosity
        
        return result


import unittest

class ColoredTextTestResult(unittest.TestResult):
    """Custom test result class that provides colored output."""
    
    def __init__(self, stream, descriptions, verbosity):
        super().__init__()
        self.stream = stream
        self.descriptions = descriptions
        self.verbosity = verbosity
        self.successes = []
    
    def startTest(self, test):
        super().startTest(test)
    
    def addSuccess(self, test):
        self.successes.append(test)
        # Print green dot for success
        self.stream.write('\033[32m.\033[0m')
        self.stream.flush()
    
    def addError(self, test, err):
        super().addError(test, err)
        self.stream.write('\033[31mE\033[0m')
        self.stream.flush()
    
    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.stream.write('\033[31mF\033[0m')
        self.stream.flush()
    
    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.stream.write('\033[33mS\033[0m')
        self.stream.flush()
    
    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.stream.write('\033[33mx\033[0m')
        self.stream.flush()
    
    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.stream.write('\033[31mu\033[0m')
        self.stream.flush()
    
    def printErrors(self):
        # Print detailed error information
        if self.errors:
            self.stream.write('\n\n')
            self.stream.write('\033[31m' + '=' * 70 + '\033[0m\n')
            self.stream.write('\033[31mERRORS\033[0m\n')
            self.stream.write('\033[31m' + '=' * 70 + '\033[0m\n')
            for test, err in self.errors:
                self.stream.write(f'\n\033[31mERROR: {test}\033[0m\n')
                self.stream.write('-' * 70 + '\n')
                self.stream.write(err)
        
        if self.failures:
            self.stream.write('\n\n')
            self.stream.write('\033[31m' + '=' * 70 + '\033[0m\n')
            self.stream.write('\033[31mFAILURES\033[0m\n')
            self.stream.write('\033[31m' + '=' * 70 + '\033[0m\n')
            for test, err in self.failures:
                self.stream.write(f'\n\033[31mFAIL: {test}\033[0m\n')
                self.stream.write('-' * 70 + '\n')
                self.stream.write(err)
    
    def printSummary(self):
        self.stream.write('\n\n')
        self.stream.write('-' * 70 + '\n')
        
        if self.wasSuccessful():
            self.stream.write(f'\033[32mRan {self.testsRun} tests in OK\033[0m\n')
        else:
            failed_count = len(self.failures) + len(self.errors)
            self.stream.write(f'\033[31mFAILED (failures={len(self.failures)}, errors={len(self.errors)})\033[0m\n')
        
        if self.skipped:
            self.stream.write(f'Skipped: {len(self.skipped)}\n')
    
    def wasSuccessful(self):
        return len(self.failures) == len(self.errors) == 0


# Monkey patch Django's test runner to use our custom result class
def patch_test_runner():
    from django.test import runner
    import unittest
    
    original_run = unittest.TextTestRunner.run
    
    def custom_run(self, test):
        result = ColoredTextTestResult(self.stream, self.descriptions, self.verbosity)
        test(result)
        result.printErrors()
        result.printSummary()
        return result
    
    unittest.TextTestRunner.run = custom_run


# Apply the patch when this module is imported
patch_test_runner()