import os
import re
import traceback
import types
from importlib import import_module, sys

from Jumpscale import j

VALID_TEST_NAME = re.compile("(?:^|[\b_\./-])[Tt]est")


class Skip(Exception):
    """Raise for skip test"""


class TestTools:
    @staticmethod
    def skip(msg):
        def dec(func):
            def wrapper(*args, **kwargs):
                raise Skip(msg)

            wrapper.__test_skip__ = True
            return wrapper

        return dec

    def run(self, path=""):
        if hasattr(self, "_dirpath") and not path:
            path = j.sal.fs.joinPaths(self._dirpath, "tests")

        if not j.sal.fs.isAbsolute(path):
            path = j.sal.fs.joinPaths(j.sal.fs.getcwd(), path)

        if ":" in path:
            if len(path.split(":")) is not 2:
                raise ValueError(f"{path} is not valid")
            else:
                path, test_name = path.split(":")
                self.discover(path, test_name)
                self._run(test_name)
        else:
            self.discover(path)
            return self._run()
        return 0

    def discover(self, path, test_name=""):
        self.modules = []
        if test_name:
            if j.sal.fs.isFile(path):
                parent_path = j.sal.fs.getDirName(path)
                sys.path.insert(0, parent_path)
                self._import_from_module(test_name, path, parent_path)
            else:
                raise ValueError(f"File {path} is not found")

        elif j.sal.fs.isFile(path):
            parent_path = j.sal.fs.getDirName(path)
            sys.path.insert(0, parent_path)
            self._import_from_file(path, parent_path)
        else:
            sys.path.insert(0, path)
            files_pathes = j.sal.fs.listPyScriptsInDir(path=path, recursive=True)
            for file_path in files_pathes:
                self._import_from_file(file_path, path)

    def _import_from_file(self, file_path, path):
        relative_path, basename, _, _ = j.sal.fs.pathParse(file_path, baseDir=path)
        if not VALID_TEST_NAME.match(basename):
            return

        dotted_path = relative_path[:-1].replace("/", ".")
        if dotted_path:
            basename = f".{basename}"
        module = import_module(name=basename, package=dotted_path)
        for mod in dir(module):
            if VALID_TEST_NAME.match(mod):
                self.modules.append(module)
                break

    def _import_from_module(self, test_name, file_path, path):
        relative_path, basename, _, _ = j.sal.fs.pathParse(file_path, baseDir=path)
        dotted_path = relative_path[:-1].replace("/", ".")
        if dotted_path:
            basename = f".{basename}"
        module = import_module(name=basename, package=dotted_path)
        self.modules.append(module)
        if test_name not in dir(module):
            raise AttributeError(f"Test {test_name} is not found")

    def _run(self, test_name=""):
        self.results = {"summary": {"passes": 0, "failures": 0, "errors": 0, "skips": 0}, "testcases": []}
        for module in self.modules:
            self.before_all(module)
            if test_name:
                self.run_test(test_name, module)
            else:
                for method in dir(module):
                    if VALID_TEST_NAME.match(method):
                        self.run_test(method, module)

            self.after_all(module)
        self.report()
        if (self.results["summary"]["failures"] > 0) or (self.results["summary"]["errors"] > 0):
            return 1

    def before_all(self, module):
        module_name = module.__file__
        if hasattr(module, "before_all"):
            before_all = getattr(module, "before_all")
            try:
                before_all()
            except Exception as error:
                self.add_helper_error(module_name, error)
                print("error\n")

    def after_all(self, module):
        module_name = module.__file__
        if hasattr(module, "after_all"):
            after_all = getattr(module, "after_all")
            try:
                after_all()
            except Exception as error:
                self.add_helper_error(module_name, error)
                print("error\n")

    def before(self, module):
        if hasattr(module, "before"):
            before = getattr(module, "before")
            before()

    def after(self, module, test_name):
        module_name = f"{module.__file__}:{test_name}"
        if hasattr(module, "after"):
            after = getattr(module, "after")
            try:
                after()
            except Exception as error:
                self.add_helper_error(module_name, error)
                print("error\n")

    def run_test(self, method, module):
        module_name = module.__file__
        test_name = f"{module_name}:{method}"
        try:
            test = getattr(module, method)
            if type(test) is not types.FunctionType:
                return
            print(test_name, "...")
            if not self._is_skipped(test):
                self.before(module)

            test()
            self.add_success(test_name)
            print("ok\n")
        except AssertionError as error:
            self.add_failure(test_name, error)
            print("fail\n")
        except Skip as sk:
            skip_msg = f"SkipTest: {sk.args[0]}\n"
            self.add_skip(test_name, skip_msg)
            print("skip\n")
        except Exception as error:
            self.add_error(test_name, error)
            print("error\n")

        self.after(module, test_name)

    def report(self):
        length = 70
        for result in self.results["testcases"]:
            msg = result["msg"].split(": ")[1]
            print(msg)
            error = result["error"].split(": ")[1]
            print(error)

        print("-" * length)
        all_tests = sum(self.results["summary"].values())
        print(f"Ran {all_tests} tests\n\n")
        result_log = j.core.tools.log(
            "{RED}%s Failed, {YELLOW}%s Errored, {GREEN}%s Passed, {BLUE}%s Skipped"
            % (
                self.results["summary"]["failures"],
                self.results["summary"]["errors"],
                self.results["summary"]["passes"],
                self.results["summary"]["skips"],
            )
        )
        result_str = j.core.tools.log2str(result_log)
        print(result_str.split(": ")[1], "\u001b[0m")

    def _is_skipped(self, test):
        if hasattr(test, "__test_skip__"):
            return getattr(test, "__test_skip__")

    def add_success(self, test_name):
        self.results["summary"]["passes"] += 1

    def add_failure(self, test_name, error):
        self.results["summary"]["failures"] += 1
        length = len(test_name) + 6
        msg = "\n" + "=" * length + "\n" + "FAIL: " + test_name + "\n" + "-" * length + "\n"
        log_msg = j.core.tools.log("{RED} %s " % msg, stdout=False)
        str_msg = j.core.tools.log2str(log_msg)
        log_error = j.core.tools.log("", exception=error, stdout=False)
        str_error = j.core.tools.log2str(log_error)
        result = {"msg": str_msg, "error": str_error}
        self.results["testcases"].append(result)

    def add_error(self, test_name, error):
        self.results["summary"]["errors"] += 1
        length = len(test_name) + 7
        msg = "\n" + "=" * length + "\n" + "ERROR: " + test_name + "\n" + "-" * length + "\n "
        log_msg = j.core.tools.log("{YELLOW} %s " % msg, stdout=False)
        str_msg = j.core.tools.log2str(log_msg)
        log_error = j.core.tools.log("", exception=error, stdout=False)
        str_error = j.core.tools.log2str(log_error)
        result = {"msg": str_msg, "error": str_error}
        self.results["testcases"].append(result)

    def add_skip(self, test_name, skip_msg):
        self.results["summary"]["skips"] += 1
        length = len(test_name) + 6
        msg = "\n" + "=" * length + "\n" + "SKIP: " + test_name + "\n" + "-" * length + "\n "
        log_msg = j.core.tools.log("{BLUE} %s " % msg, stdout=False)
        str_msg = j.core.tools.log2str(log_msg)
        skip_msg = "\n" + skip_msg + "\n"
        log_skip = j.core.tools.log("{BLUE} %s " % skip_msg, stdout=False)
        str_skip = j.core.tools.log2str(log_skip)
        result = {"msg": str_msg, "error": str_skip}
        self.results["testcases"].append(result)

    def add_helper_error(self, test_name, error):
        length = len(test_name) + 7
        msg = "\n" + "=" * length + "\n" + "ERROR: " + test_name + "\n" + "-" * length + "\n "
        log_msg = j.core.tools.log("{YELLOW} %s " % msg, stdout=False)
        str_msg = j.core.tools.log2str(log_msg)
        log_error = j.core.tools.log("", exception=error, stdout=False)
        str_error = j.core.tools.log2str(log_error)
        result = {"msg": str_msg, "error": str_error}
        self.results["testcases"].append(result)
