"""Checks for count_paper_coauthors and the pubmed-coauthor-paper-count task."""

from .checks import result
from .names import input_problem, output_problem
from .record import load_record


def verify_input(value):
    problem = input_problem(value)
    if problem:
        return result(False, problem[1])
    return result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    problem = input_problem(input_value) or output_problem(output_value)
    if problem:
        return result(False, problem[1])
    kind, payload = load_record(workspace, input_value)
    if kind != "ok":
        return result(False, payload)
    if output_value.coauthor_count != payload["coauthor_count"]:
        return result(False, "output is not the count in coauthors.json")
    return result(True, "output matches the recorded count")


def verify_task(arguments, output, reference, workspace):
    problem = input_problem(arguments) or output_problem(output)
    if problem:
        return result(False, problem[1])
    # A tool run never receives the pin. Judge that call from coauthors.json.
    if reference is not None:
        problem = output_problem(reference)
        if problem:
            return result(False, problem[1])
        if output.coauthor_count != reference.coauthor_count:
            return result(False, "output does not match the reference")
    kind, payload = load_record(workspace, arguments)
    if kind != "ok":
        return result(False, payload)
    if output.coauthor_count != payload["coauthor_count"]:
        return result(False, "coauthors.json does not support the output")
    if reference is None:
        return result(True, "output matches the recorded count")
    return result(True, "output matches the reference")
