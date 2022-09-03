from zrunner import ZRunner
from argparse import ArgumentParser


parser = ArgumentParser()
parser.add_argument("path", action="store", type=str, help="The text to parse.")
parser.add_argument(
    "--log-level",
    action="store",
    dest="log_level",
    default="INFO",
    type=str,
    help='log level for the result allowed levels ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]',
)
parser.add_argument(
    "--xml-report",
    default=False,
    action="store_true",
    dest="xml_report",
    help="Generate xml report after running the tests",
)
parser.add_argument(
    "--xml-path",
    action="store",
    dest="xml_path",
    default="test.xml",
    type=str,
    help="xml result file's path",
)
parser.add_argument(
    "--xml-testsuite-name",
    action="store",
    dest="xml_testsuite_name",
    default="Zero Runner",
    type=str,
    help="xml result testsuite name",
)
args = parser.parse_args()
def run():
    t = ZRunner(
        log_level=args.log_level,
        xml_report=args.xml_report,
        xml_path=args.xml_path,
        xml_testsuite_name=args.xml_testsuite_name,
    )
    splits = args.path.split(":")
    if len(splits) == 1:
        t.run_from_path(splits[0])
    elif len(splits) == 2:
        t.run_from_path(splits[0], splits[1])
    else:
        raise Exception("Invalid path")


run()
