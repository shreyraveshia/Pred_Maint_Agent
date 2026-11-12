import pytest
from contracts.permissions import check_tool, PermissionDenied


def test_allowed_tools():
    assert check_tool("get_asset") == "read"
    assert check_tool("create_draft_work_order") == "draft_write"


@pytest.mark.parametrize("tool", ["approve_work_order", "delete_work_order", "drop_table"])
def test_denied_tools(tool):
    with pytest.raises(PermissionDenied):
        check_tool(tool)
