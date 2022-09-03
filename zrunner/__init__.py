import logging
import os
import re
import time
import traceback
import types
from cmath import log
from importlib import import_module, sys

COLORS = {
    "RED": "\033[1;31m",
    "BLUE": "\033[1;34m",
    "CYAN": "\033[1;36m",
    "GREEN": "\033[0;32m",
    "GRAY": "\033[0;37m",
    "YELLOW": "\033[0;33m",
    "RESET": "\033[0;0m",
    "BOLD": "\033[;1m",
    "REVERSE": "\033[;7m",
}
_VALID_TEST_NAME = re.compile("(?:^|[\b_\./-])[Tt]est")
_FAIL_LENGTH = 6
_ERROR_LENGTH = 7


_full_results = {"summary": {"passes": 0, "failures": 0, "errors": 0, "skips": 0}, "testcases": [], "time_taken": 0}


class Skip(Exception):
    """Raise for skipping test"""


class ZRunner:
    __show_tests_report = True
    _modules = []
    _results = {"summary": {"passes": 0, "failures": 0, "errors": 0, "skips": 0}, "testcases": [], "time_taken": 0}

    def __init__(self, log_level=logging.INFO, xml_report=False, xml_path="test.xml", xml_testsuite_name="Zero Runner"):
        self._xml_report = xml_report
        self._xml_path = xml_path
        self._xml_testsuite_name = xml_testsuite_name
        self.log_level = log_level
        self.setup_logs()

    def setup_logs(self):
        logging.root.setLevel(self.log_level)
        self.logger = logging.getLogger("pythonConfig")
        self.logger.setLevel(self.log_level)

    def log(self, log_level, msg):
        self.logger.log(log_level, msg)

    @staticmethod
    def _skip(msg):
        """Skip is used as a decorator to skip tests with a message.

        :param msg: string message for final report.
        """

        def dec(func):
            def wrapper(*args, **kwargs):
                raise Skip(msg)

            wrapper.__name__ = func.__name__
            wrapper.__test_skip__ = True
            return wrapper

        return dec

    def run_from_path(self, path="", name=""):
        """Run tests from absolute or relative path.

        :param path: tests path.
        :param name: testcase name to be run in case of running only one test.
        """
        self._reset(modules=False)
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        self._discover_from_path(path, name)
        return self._execute_report_tests(name)

    def _reset(self, modules=True, full=False):
        """Reset the test runner (results and modules has been discovered).

        :param modules: True to reset the modules.
        :param full: True to reset local and global results.
        """
        if full:
            for module in self._modules:
                module.__show_tests_report = True

            global _full_results
            _full_results = {
                "summary": {"passes": 0, "failures": 0, "errors": 0, "skips": 0},
                "testcases": [],
                "time_taken": 0,
            }
        if modules:
            self._modules = []
        self._results = {
            "summary": {"passes": 0, "failures": 0, "errors": 0, "skips": 0},
            "testcases": [],
            "time_taken": 0,
        }

    def _list_python_files(self, path):
        files_paths = []
        for root, _, files in os.walk(path):
            for name in files:
                if name.endswith(".py"):
                    file_path = os.path.join(root, name)
                    files_paths.append(file_path)
        return files_paths

    def _discover_from_path(self, path, test_name=""):
        """Discover and get modules that contains tests in a certain path.

        :param path: absolute path to be discovered.
        :param test_name: (optional) test name for getting only this test.
        """
        self._reset()
        if os.path.isfile(path):
            parent_path = os.path.dirname(path)
            sys.path.insert(0, parent_path)
            if test_name:
                self._import_test_module(test_name, path, parent_path)
            else:
                self._import_file_module(path, parent_path)
        else:
            sys.path.insert(0, path)
            files_paths = self._list_python_files(path)
            for file_path in files_paths:
                file_path_base = os.path.basename(file_path)
                if not file_path_base.startswith("_"):
                    self._import_file_module(file_path, path)

    def _import_file_module(self, file_path, path):
        """Import module (file) if module contains a test.

        :param file_path: absolute file path.
        :param path: absolute path for one of file's parents.
        """
        basename_with_extension = file_path.split("/")[-1]
        basename = basename_with_extension.rstrip(".py")
        if path != "":
            relative_path = file_path.split(path)[1]
        relative_path = relative_path.split(basename_with_extension)[0]

        dotted_path = relative_path[:-1].replace("/", ".")
        if dotted_path:
            basename = f".{basename}"
        module = import_module(name=basename, package=dotted_path)
        for mod in dir(module):
            if _VALID_TEST_NAME.match(mod):
                self._modules.append(module)
                break

    def _import_test_module(self, test_name, file_path, path):
        """Import module (test) from file path.

        :param test_name: test name to be imported.
        :param file_path: absolute file path.
        :param path: absolute path for one of the file's parents.
        """
        basename_with_extension = file_path.split("/")[-1]
        basename = basename_with_extension.rstrip(".py")
        if path != "":
            relative_path = file_path.split(path)[1]
        relative_path = relative_path.split(basename_with_extension)[0]

        dotted_path = relative_path[:-1].replace("/", ".")
        if dotted_path:
            basename = f".{basename}"
        module = import_module(name=basename, package=dotted_path)
        self._modules.append(module)
        if test_name not in dir(module):
            raise AttributeError(f"Test {test_name} is not found")

    def _execute_report_tests(self, test_name="", report=True):
        """Run tests has been discovered using a discover method.

        :param test_name: (optional) test name for run only this test.
        :return: 0 in case of success or no test found, 1 in case of failure.
        """
        # We should keep track of every test (execution time)
        start_time = time.time()
        for module in self._modules:
            skip = self._before_all(module)
            if skip:
                continue
            if test_name:
                self._execute_test(test_name, module)
            else:
                for method in dir(module):
                    if not method.startswith("_") and _VALID_TEST_NAME.match(method):
                        self._execute_test(method, module)

            self._after_all(module)
        end_time = time.time()
        time_taken = end_time - start_time
        self._results["time_taken"] = time_taken
        fail_status = (self._results["summary"]["failures"] > 0) or (self._results["summary"]["errors"] > 0)
        if report and self.__show_tests_report:
            # in case of running test from path or jsx factory.
            self._report()
            self._reset()
        if not self.__show_tests_report:
            # in case of collecting all tests to be reported at the end.
            self._add_to_full_results()
            self._reset(modules=False)

        if fail_status:
            return 1
        return 0

    def _execute_test(self, method, module):
        """Execute one test.

        :param method: test name.
        :param module: module that contain this test.
        """
        module_location = self._get_module_location(module)
        test_name = f"{module_location}.{method}"

        try:
            test = getattr(module, method)
            if not isinstance(test, (types.FunctionType, types.MethodType)):
                return
            self.log(logging.DEBUG, f"{test_name}...")
            if not self._is_skipped(test):
                self._before(module)
            test()
            self._add_success(test_name)
        except AssertionError as error:
            self._add_failure(test_name, error)

        except Skip as sk:
            skip_msg = f"SkipTest: {sk.args[0]}\n"
            self._add_skip(test_name, skip_msg)

        except BaseException as error:
            self._add_error(test_name, error)

        if not self._is_skipped(test):
            self._after(module, test_name)

    def _get_module_location(self, module):
        if hasattr(module, "_location"):
            module_location = module._location
        else:
            module_location = module.__file__

        return module_location

    def _before_all(self, module):
        """Get and execute before_all in a module if it is exist.

        :param module: module that contains before_all.
        """
        self._start_time = time.time()
        module_location = self._get_module_location(module)
        if "before_all" in dir(module):
            before_all = getattr(module, "before_all")
            try:
                before_all()
            except Skip as sk:
                self.log(logging.DEBUG, f"{module_location} ...")
                skip_msg = f"SkipTest: {sk.args[0]}\n"
                self._add_skip(module_location, skip_msg)
                return True
            except BaseException as error:
                self._add_helper_error(module_location, error)
                self.log(logging.DEBUG, "error\n")

        return False

    def _after_all(self, module):
        """Get and execute after_all in a module if it is exist.

        :param module: module that contains after_all.
        """
        module_location = self._get_module_location(module)
        if "after_all" in dir(module):
            after_all = getattr(module, "after_all")
            try:
                after_all()
            except BaseException as error:
                self._add_helper_error(module_location, error)
                self.log(logging.DEBUG, "error\n")

    def _before(self, module):
        """Get and execute before in a module if it is exist.

        :param module: module that contains before.
        """
        self._start_time = time.time()
        if "before" in dir(module):
            before = getattr(module, "before")
            before()

    def _after(self, module, test_name):
        """Get and execute after in a module if it is exist.

        :param module: module that contains after.
        """
        if "after" in dir(module):
            after = getattr(module, "after")
            try:
                after()
            except BaseException as error:
                self._add_helper_error(test_name, error)
                self.log(logging.DEBUG, "error\n")

    def _is_skipped(self, test):
        """Check if the test is skipped.

        :param test: test method.
        """
        if hasattr(test, "__test_skip__"):
            return getattr(test, "__test_skip__")

    def _add_success(self, test_name):
        """Add a succeed test."""
        time_taken = self._time_taken()
        self._results["summary"]["passes"] += 1
        result = {"name": test_name, "status": "passed", "time": time_taken}
        self._results["testcases"].append(result)
        self.log(logging.DEBUG, "ok\n")

    def _add_failure(self, test_name, error):
        """Add a failed test.

        :param error: test exception error.
        """
        time_taken = self._time_taken()
        self._results["summary"]["failures"] += 1
        length = len(test_name) + _FAIL_LENGTH
        msg = "=" * length + f"\nFAIL: {test_name}\n" + "-" * length
        str_msg = "{RED}{msg}{RESET}".format(msg=msg, **COLORS)
        trace_back = traceback.format_exc()
        str_error = "{RED}{msg}{RESET}".format(msg=f"{error}\n{trace_back}", **COLORS)
        result = {
            "name": test_name,
            "traceback": trace_back,
            "msg": str_msg,
            "error": str_error,
            "status": "failure",
            "time": time_taken,
        }
        self._results["testcases"].append(result)
        self.log(logging.DEBUG, "fail\n")

    def _add_error(self, test_name, error):
        """Add a errored test.

        :param error: test exception error.
        """
        time_taken = self._time_taken()
        self._results["summary"]["errors"] += 1
        length = len(test_name) + _ERROR_LENGTH
        msg = "=" * length + f"\nERROR: {test_name}\n" + "-" * length
        str_msg = "{YELLOW}{msg}{RESET}".format(msg=msg, **COLORS)
        trace_back = traceback.format_exc()
        str_error = "{YELLOW}{msg}{RESET}".format(msg=f"{error}\n{trace_back}", **COLORS)
        result = {
            "name": test_name,
            "traceback": trace_back,
            "msg": str_msg,
            "error": str_error,
            "status": "error",
            "time": time_taken,
        }
        self._results["testcases"].append(result)
        self.log(logging.DEBUG, "error\n")

    def _add_skip(self, test_name, skip_msg):
        """Add a skipped test.

        :param skip_msg: reason for skipping the test.
        """
        time_taken = self._time_taken()
        self._results["summary"]["skips"] += 1
        length = len(test_name) + _FAIL_LENGTH
        msg = "=" * length + f"\nSKIP: {test_name}\n" + "-" * length
        str_msg = "{BLUE}{msg}{RESET}".format(msg=msg, **COLORS)
        str_skip = "{BLUE}{msg}{RESET}".format(msg=skip_msg, **COLORS)
        result = {
            "name": test_name,
            "message": skip_msg,
            "msg": str_msg,
            "error": str_skip,
            "status": "skipped",
            "time": time_taken,
        }
        self._results["testcases"].append(result)
        self.log(logging.DEBUG, "skip\n")

    def _add_helper_error(self, test_name, error):
        """Add error that happens in a helper method (before_all, after, after_all).

        :param error: test exception error.
        """
        time_taken = self._time_taken()
        length = len(test_name) + _ERROR_LENGTH
        msg = "=" * length + f"\nERROR: {test_name}\n" + "-" * length
        str_msg = "{YELLOW}{msg}{RESET}".format(msg=msg, **COLORS)
        trace_back = traceback.format_exc()
        str_error = "{RED}{msg}{RESET}".format(msg=f"{error}\n{trace_back}", **COLORS)
        result = {
            "name": test_name,
            "traceback": trace_back,
            "msg": str_msg,
            "error": str_error,
            "status": "error",
            "time": time_taken,
        }
        self._results["testcases"].append(result)

    def _time_taken(self):
        diff_time = time.time() - self._start_time
        time_taken = "{0:.5f}".format(diff_time)
        return time_taken

    def _report(self, results=None):
        """Collect and print the final report."""
        if not results:
            results = self._results

        testcases_results = sorted(results["testcases"], key=lambda x: x["status"], reverse=True)
        for result in testcases_results:
            if result["status"] == "passed":
                continue

            msg = result["msg"]
            self.log(logging.ERROR, msg)
            error = result["error"]
            self.log(logging.ERROR, error)

        self.log(logging.CRITICAL, "-" * 70)  # line To print the summary
        all_tests = sum(results["summary"].values())
        time_taken = "{0:.5f}".format(results["time_taken"])
        self.log(logging.CRITICAL, f"Ran {all_tests} tests in {time_taken}\n\n")
        result_str = "{RED}{failures} Failed, {YELLOW}{errors} Errored, {GREEN}{passes} Passed, {BLUE}{skips} Skipped{RESET}".format(
            failures=results["summary"]["failures"],
            errors=results["summary"]["errors"],
            passes=results["summary"]["passes"],
            skips=results["summary"]["skips"],
            **COLORS,
        )
        self.log(logging.CRITICAL, result_str)
        self._generate_xml(results)

    def _add_to_full_results(self):
        """Add results from test runner to full result to report them once at the end."""
        global _full_results
        _full_results["summary"]["failures"] += self._results["summary"]["failures"]
        _full_results["summary"]["errors"] += self._results["summary"]["errors"]
        _full_results["summary"]["passes"] += self._results["summary"]["passes"]
        _full_results["summary"]["skips"] += self._results["summary"]["skips"]
        _full_results["time_taken"] += self._results["time_taken"]
        _full_results["testcases"].extend(self._results["testcases"])

    def _generate_xml(self, results=None):
        """Generate xml report for the last running tests in case of _xml_report is True.
            _xml_path: should be set at the object to determine xml file path (default: test.xml in the current working directory)
            _xml_testsuite_name: should be set at the object to determine testsuite name (default: Jsx Runner)

        :param results: jsx runner result to be converted from dict to xml.
        """
        import xmltodict

        if results is None:
            results = self._results

        if "_xml_report" in dir(self) and self._xml_report:
            testsuite_name = self._xml_testsuite_name
            path = self._xml_path
            all_tests = sum(results["summary"].values())
            all_results = {
                "testsuite": {
                    "name": testsuite_name,
                    "tests": all_tests,
                    "failures": results["summary"]["failures"],
                    "errors": results["summary"]["errors"],
                    "skip": results["summary"]["skips"],
                    "testcase": [],
                }
            }
            for result in results["testcases"]:
                needed_result = {"name": result["name"], "time": result["time"]}
                if result["status"] != "passed":
                    if result["status"] == "skipped":
                        needed_result[result["status"]] = {"message": result["message"]}
                    else:
                        needed_result[result["status"]] = {"content": result["traceback"]}

                all_results["testsuite"]["testcase"].append(needed_result)
            data = xmltodict.unparse(all_results)
            with open(path, "w") as f:
                f.write(data)
            self.log(logging.CRITICAL, "-" * 70)
            if not os.path.isabs(path):
                path = os.path.join(os.getcwd(), path)
            self.log(logging.CRITICAL, f"XML file has been generated in {path}")
            self.log(logging.CRITICAL, "-" * 70)


skip = ZRunner._skip
