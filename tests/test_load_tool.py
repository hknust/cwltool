import pytest
import pkg_resources

from cwltool.context import LoadingContext, RuntimeContext
from cwltool.errors import WorkflowException
from cwltool.load_tool import load_tool
from cwltool.resolver import Path, resolve_local
from cwltool.update import INTERNAL_VERSION
from cwltool.process import (
    use_custom_schema,
    use_standard_schema,
)

from .test_fetch import norm
from .util import (
    get_data,
    get_main_output,
    get_windows_safe_factory,
    needs_docker,
    needs_singularity,
    temp_dir,
    windows_needs_docker,
    working_directory,
)


@windows_needs_docker
def test_check_version():
    """
    It is permitted to load without updating, but not execute.

    Attempting to execute without updating to the internal version should raise an error.
    """
    joborder = {"inp": "abc"}
    loadingContext = LoadingContext({"do_update": True})
    tool = load_tool(get_data("tests/echo.cwl"), loadingContext)
    for j in tool.job(joborder, None, RuntimeContext()):
        pass

    loadingContext = LoadingContext({"do_update": False})
    tool = load_tool(get_data("tests/echo.cwl"), loadingContext)
    with pytest.raises(WorkflowException):
        for j in tool.job(joborder, None, RuntimeContext()):
            pass


def test_use_metadata():
    """Use the version from loadingContext.metadata if cwlVersion isn't present in the document."""
    loadingContext = LoadingContext({"do_update": False})
    tool = load_tool(get_data("tests/echo.cwl"), loadingContext)

    loadingContext = LoadingContext()
    loadingContext.metadata = tool.metadata
    tooldata = tool.tool.copy()
    del tooldata["cwlVersion"]
    tool2 = load_tool(tooldata, loadingContext)


def test_checklink_outputSource():
    """Is outputSource resolved correctly independent of value of do_validate."""
    outsrc = (
        norm(Path(get_data("tests/wf/1st-workflow.cwl")).as_uri())
        + "#argument/classfile"
    )

    loadingContext = LoadingContext({"do_validate": True})
    tool = load_tool(get_data("tests/wf/1st-workflow.cwl"), loadingContext)
    assert norm(tool.tool["outputs"][0]["outputSource"]) == outsrc

    loadingContext = LoadingContext({"do_validate": False})
    tool = load_tool(get_data("tests/wf/1st-workflow.cwl"), loadingContext)
    assert norm(tool.tool["outputs"][0]["outputSource"]) == outsrc


def test_load_graph_fragment():
    """Reloading from a dictionary without a cwlVersion."""
    loadingContext = LoadingContext()
    uri = Path(get_data("tests/wf/scatter-wf4.cwl")).as_uri() + "#main"
    tool = load_tool(uri, loadingContext)

    rs, metadata = tool.doc_loader.resolve_ref(uri)
    # Reload from a dict (in 'rs'), not a URI.  The dict is a fragment
    # of original document and doesn't have cwlVersion set, so test
    # that it correctly looks up the root document to get the
    # cwlVersion.
    tool = load_tool(rs, loadingContext)
    assert tool.metadata["cwlVersion"] == INTERNAL_VERSION


def test_load_graph_fragment_from_packed():
    """Loading a fragment from packed with update."""
    loadingContext = LoadingContext()
    uri = Path(get_data("tests/wf/packed-with-loadlisting.cwl")).as_uri() + "#main"
    try:
        with open(get_data("cwltool/extensions.yml"), "r") as res:
            use_custom_schema("v1.0", "http://commonwl.org/cwltool", res.read())

        # The updater transforms LoadListingRequirement from an
        # extension (in v1.0) to a core feature (in v1.1) but there
        # was a bug when loading a packed workflow and loading a
        # specific fragment it would get the un-updated document.
        # This recreates that case and asserts that we are using the
        # updated document like we should.

        tool = load_tool(uri, loadingContext)

        assert tool.tool["requirements"] == [
            {"class": "LoadListingRequirement", "loadListing": "no_listing"}
        ]
    finally:
        use_standard_schema("v1.0")
