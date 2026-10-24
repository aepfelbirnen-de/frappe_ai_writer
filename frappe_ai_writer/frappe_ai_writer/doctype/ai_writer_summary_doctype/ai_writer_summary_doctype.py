# Copyright (c) 2026, aepfel+birnen IT GmbH and contributors
# For license information, please see license.txt

from __future__ import annotations

from frappe.model.document import Document


class AIWriterSummaryDocType(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        document_type: DF.Link
        parent: DF.Data
        parentfield: DF.Data
        parenttype: DF.Data
    # end: auto-generated types

    pass
