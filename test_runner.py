from Jumpscale import j
from importlib import import_module, sys
import os
import re
import traceback
import types

VALID_TEST_NAME = re.compile("(?:^|[\b_\./-])[Tt]est")


class Skip(Exception):
    """Raise for skip test"""


def skip(msg):
    def dec(func):
        def wrapper(*args, **kwargs):
            raise Skip(msg)

        wrapper.__test_skip__ = True
        return wrapper

    return dec


class TestTool:
    def run(self, path):
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
            self._run()

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
        self.results = {"summary": {"passed": 0, "failures": 0, "errors": 0, "skips": 0}, "testcases": []}
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

    def before_all(self, module):
        module_name = module.__file__
        if hasattr(module, "before_all"):
            before_all = getattr(module, "before_all")
            try:
                before_all()
            except:
                trace_back = traceback.format_exc()
                self.add_helper_error(module_name, trace_back)
                print("error\n")

    def after_all(self, module):
        module_name = module.__file__
        if hasattr(module, "after_all"):
            after_all = getattr(module, "after_all")
            try:
                after_all()
            except:
                trace_back = traceback.format_exc()
                self.add_helper_error(module_name, trace_back)
                print("error\n")

    def before(self, module):
        if hasattr(module, "before"):
            before = getattr(module, "before")
        else:
            before = self.pass_method
        return before

    def after(self, module, test_name):
        module_name = f"{module.__file__}:{test_name}"
        if hasattr(module, "after"):
            after = getattr(module, "after")
            try:
                after()
            except:
                trace_back = traceback.format_exc()
                self.add_helper_error(module_name, trace_back)
                print("error\n")

    def run_test(self, method, module):
        module_name = module.__file__
        test_name = f"{module_name}:{method}"
        before = self.before(module)
        try:
            test = getattr(module, method)
            if type(test) is not types.FunctionType:
                return
            print(test_name, "...")
            if not self._is_skipped(test):
                before()

            test()
            self.add_success(test_name)
            print("ok\n")
        except AssertionError:
            trace_back = traceback.format_exc()
            self.add_failure(test_name, trace_back)
            print("fail\n")
        except Skip as sk:
            skip_msg = f"SkipTest: {sk.args[0]}\n"
            self.add_skip(test_name, skip_msg)
            print("skip\n")
        except Exception:
            trace_back = traceback.format_exc()
            self.add_error(test_name, trace_back)
            print("error\n")

        self.after(module, test_name)

    def report(self):
        length = 70
        for testcase in self.results["testcases"]:
            if testcase.get("details"):
                print("=" * length)
                print(f'{testcase["status"].upper()}:', testcase["name"])
                print("-" * length)
                print(testcase["details"])

        print("-" * length)
        all_tests = sum(self.results["summary"].values())
        print(f"Ran {all_tests}\n\n")
        print(
            "{failed} Failed, {error} Error, {passed} Passed, {skip} Skip".format(
                failed=self.results["summary"]["failures"],
                error=self.results["summary"]["errors"],
                passed=self.results["summary"]["passed"],
                skip=self.results["summary"]["skips"],
            )
        )

    def pass_method(self):
        pass

    def _is_skipped(self, test):
        if hasattr(test, "__test_skip__"):
            return getattr(test, "__test_skip__")

    def add_success(self, test_name):
        self.results["summary"]["passed"] += 1
        result = {"name": test_name, "status": 'Passed'}
        self.results["testcases"].append(result)

    def add_failure(self, test_name, trace_back):
        self.results["summary"]["failures"] += 1
        result = {"name": test_name, "status": 'Failed', "details": trace_back}
        self.results["testcases"].append(result)

    def add_error(self, test_name, trace_back):
        self.results["summary"]["errors"] += 1
        result = {"name": test_name, "status": 'Error', "details": trace_back}
        self.results["testcases"].append(result)

    def add_skip(self, test_name, skip_msg):
        self.results["summary"]["skips"] += 1
        result = {"name": test_name, "status": 'Skip', "details": skip_msg}
        self.results["testcases"].append(result)

    def add_helper_error(self, test_name, trace_back):
        result = {"name": test_name, "status": 'Error', "details": trace_back}
        self.results["testcases"].append(result)


if __name__ == "__main__":
    l = TestTool()
    path = sys.argv[1]
    l.run(path="/sandbox/code/github/threefoldtech/jumpscaleX_libs/test")
