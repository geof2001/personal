"""Unit tests."""
import unittest
from StringIO import StringIO
import cmds.cmd_inputs as cmd_inputs


class SlackBudTestCase(unittest.TestCase):

    # Add new unit tests to this file by including a class method
    # that starts with 'test'
    # Verify results with assert.
    # Results of tests are logged to '/aws/lambda/pipeline-run-tests'
    # in the INFRA account.
    # If unit tests fail that don't get past the RunTest step in the
    # pipeline

    # This test deliberately fails. Uncomment to verify the negative test case.
    # def testDeliberateError(self):
    #     """A deliberate error to verify works in pipeline framework"""
    #     self.assertTrue(False, 'This is a deliberate failed test.')

    def testDeliberateSuccess(self):
        """A deliberate success as parr to verifying pipeline framework"""
        self.assertTrue(True, 'Deliberate successful test.')

    def testCmdInputSerialization(self):
        no_exception = cmd_inputs.test_serialize_deserialize_main()
        self.assertTrue(no_exception, 'Serialization test exception')


def run_test():
    """
    This method is called from the RunTests stage of the
    SlackBud pipeline. The results of the unit test are pipe
    into a text stream.  The the string "AssertionError" is found
    in the output stream the unit tests are assumed to fail and this
    method throws an exception caught by the pipeline.

    This produces the same result as main, which can be called
    from the command line or within an IDE.

    :return: None or raise AssertionError
    """
    print('run_test()')
    # Do test runner and pipe details to log, but throw an error
    # if a failure is detected.
    # unittest.main()
    stream = StringIO()
    runner = unittest.TextTestRunner(
        stream=stream,
        descriptions=True,
        verbosity=1
    )
    suite = unittest.makeSuite(SlackBudTestCase)
    result = runner.run(suite)
    print('Unit Tests: {}'.format(result.testsRun))
    print('Errors: {}'.format(result.errors))
    stream.seek(0)
    test_output = 'Output:\n{}'.format(stream.read())

    if "AssertionError" in test_output:
        print('Details of unit test failure:\n{}'.format(test_output))
        print('^^^^  A unit tests failed. Output above. ^^^^')
        raise AssertionError('Unit Test failures. Check logs')
    else:
        print('All unit tests passed.')


if __name__ == '__main__':
    """
    Same method as 'run_test' for the command line or IDE.
    """
    print('main()')
    unittest.main()
